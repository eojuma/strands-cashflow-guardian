"""Orchestrator agent — the only agent that talks to external triggers.

Day 1 proved a single Bedrock call through the Strands Agents SDK. Day 3 extends
that skeleton into real multi-agent orchestration: the Orchestrator now routes
events to specialist sub-agents exposed as Strands *tools* (the "agents-as-tools"
pattern), rather than calling functions inline.

Run locally with:

    python agents/orchestrator.py

The run needs real Bedrock access (``.env``); without it the model call fails
loudly. Structural wiring is covered by ``tests/test_orchestrator.py``, which
runs with a model-id string and no network call.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from strands import Agent
from strands.models import BedrockModel

from agents.tools import build_sub_agent_tools
from agents.tools.gmail_tool import send_email as _gmail_send_email
from memory import dynamo_client, schema

DEFAULT_MODEL_ID = "anthropic.claude-3-5-sonnet-20241022-v2:0"

ORCHESTRATOR_NAME = "CashflowGuardian Orchestrator"
ORCHESTRATOR_DESCRIPTION = (
    "Routes scheduled events to specialist sub-agents and reports what they propose."
)

ORCHESTRATOR_SYSTEM_PROMPT = """\
You are the CashflowGuardian Orchestrator.

You receive a scheduled-check trigger and must route each event to the correct
specialist tool:

- A milestone-complete event -> delegate to the `invoice_dunning` tool.
- Scope-creep detection arrives on a later day; do not invent it yet.

Never draft or send anything yourself. Always delegate to the specialist tool and
report back exactly what the specialist proposed.
"""

# A hardcoded fake trigger for the Day 3 demo: proves the Orchestrator routes a
# milestone-complete event to the Invoice & Dunning specialist.
FAKE_TRIGGER = (
    "run scheduled check: milestone complete for client_001 "
    "(milestone: 'Landing page', amount: 1200.00, completed: 2026-08-23)"
)


def _load_env() -> None:
    """Load ``.env`` from the repo root if present (the file is never committed)."""
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        load_dotenv(env_path)


def build_model() -> BedrockModel:
    """Build the configured Bedrock model from the environment."""
    model_id = os.getenv("BEDROCK_MODEL_ID", DEFAULT_MODEL_ID)
    if not model_id:
        raise SystemExit(
            "BEDROCK_MODEL_ID is not set. Copy .env.example to .env and fill it in."
        )
    return BedrockModel(model_id=model_id, temperature=0.3, streaming=False)


def build_orchestrator(model: Any = None) -> Agent:
    """Build the Orchestrator with specialist sub-agents registered as tools.

    ``model`` may be a Strands ``Model`` instance, a Bedrock model-id string, or
    ``None`` (build the configured Bedrock model). Passing a string keeps this
    function testable without any AWS call.
    """
    if model is None:
        model = build_model()

    return Agent(
        name=ORCHESTRATOR_NAME,
        description=ORCHESTRATOR_DESCRIPTION,
        model=model,
        system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
        tools=build_sub_agent_tools(model),
    )


def run(trigger: str | None = None) -> str:
    """Run one orchestration pass and return the delegated output as text."""
    model = build_model()
    orchestrator = build_orchestrator(model)
    prompt = trigger if trigger is not None else FAKE_TRIGGER

    result = orchestrator(prompt)
    output = str(result)

    # Log clearly enough to demo "orchestration" later without extra work.
    print(f"[orchestrator] trigger: {prompt}")
    print(f"[orchestrator] specialist tools: {sorted(orchestrator.tool_names)}")
    print(f"[orchestrator] delegated output:\n{output}")
    return output


# ---------------------------------------------------------------------------
# Human-in-the-loop state machine (Days 11-12)
#
# The deterministic shell: proposed actions are persisted as ``pending``; only
# after a human approves/edits them does ``execute_action`` perform the external
# side effect. The LLM is never re-invoked on the resolution path.
# ---------------------------------------------------------------------------
def _default_send_email(to: str, subject: str, body: str) -> bool:
    """Default external-action executor (real Gmail send; requires credentials)."""
    return _gmail_send_email(to, subject, body)


def persist_proposed_actions(proposed_actions: list[dict]) -> list[dict]:
    """Persist proposed actions as ``pending`` (nothing is executed here)."""
    return [dynamo_client.create_pending_action(a) for a in proposed_actions]


def execute_action(action_id: str, send_fn=None) -> bool:
    """Execute a single action if (and only if) its status is approved/edited.

    This is the hard guard from docs/ARCHITECTURE.md §7: it re-reads the persisted
    status and refuses to run unless it is ``approved`` or ``edited``. Returns
    ``True`` when the action was executed, ``False`` otherwise.
    """
    if send_fn is None:
        send_fn = _default_send_email

    action = dynamo_client.get_pending_action(action_id)
    if action is None:
        return False
    if action.get(schema.ACTION_STATUS) not in (schema.STATUS_APPROVED, schema.STATUS_EDITED):
        return False

    client = dynamo_client.get_client(action.get(schema.CLIENT_ID, "")) or {}
    send_fn(
        to=client.get(schema.EMAIL, ""),
        subject=action.get(schema.ACTION_TYPE, ""),
        body=action.get(schema.DRAFTED_CONTENT, ""),
    )
    dynamo_client.update_action_status(action_id, schema.STATUS_EXECUTED)
    return True


def resolve_action(
    action_id: str, decision: str, edited_content: str | None = None, send_fn=None
) -> dict | None:
    """Apply an approve / edit / reject decision to a pending action.

    Idempotent: once an action has left ``pending`` it is left untouched.
    Rejection halts with no side effects; approval/editing then executes the
    action through :func:`execute_action`.
    """
    action = dynamo_client.get_pending_action(action_id)
    if action is None or action.get(schema.ACTION_STATUS) != schema.STATUS_PENDING:
        return action

    if decision == "rejected":
        dynamo_client.update_action_status(action_id, schema.STATUS_REJECTED)
        return dynamo_client.get_pending_action(action_id)

    if decision == "approved":
        dynamo_client.update_action_status(action_id, schema.STATUS_APPROVED)
    elif decision == "edited":
        dynamo_client.update_action_content(action_id, edited_content)
        dynamo_client.update_action_status(action_id, schema.STATUS_EDITED)
    else:
        return action  # unknown decision -> no side effects

    execute_action(action_id, send_fn=send_fn)
    return dynamo_client.get_pending_action(action_id)


def main() -> None:
    _load_env()
    run()


if __name__ == "__main__":
    main()
