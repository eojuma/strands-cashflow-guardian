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


def main() -> None:
    _load_env()
    run()


if __name__ == "__main__":
    main()
