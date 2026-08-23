"""Shared tool registration pattern for specialist sub-agents.

CashflowGuardian's specialist agents (Invoice & Dunning, Scope Creep Sentinel)
are exposed to the Orchestrator as Strands *tools* via ``Agent.as_tool()`` — the
"agents-as-tools" pattern — never as inline function calls or ``if/else`` routing
in the Orchestrator.

Delegation behind ``as_tool()`` keeps the Orchestrator as the single auditable
point of control: every externally-visible action still flows through it, while
each specialist's own model does the domain reasoning. To add a new specialist,
return its ``as_tool()`` from :func:`build_sub_agent_tools`.
"""

from __future__ import annotations

from typing import Any


def build_sub_agent_tools(model: Any) -> list[Any]:
    """Build each specialist agent and wrap it as a Strands tool.

    ``model`` is passed straight through to each specialist (a ``Model`` instance
    or a Bedrock model-id string). Specialist imports are local to avoid a
    circular import (``invoice_dunning`` imports ``agents.tools.pdf_tool``).
    """
    from agents.invoice_dunning import build_invoice_dunning_agent
    from agents.scope_sentinel import build_scope_sentinel_agent

    invoice_dunning = build_invoice_dunning_agent(model)
    scope_sentinel = build_scope_sentinel_agent(model)

    return [
        invoice_dunning.as_tool(
            name="invoice_dunning",
            description=(
                "Delegate milestone-complete events here. Returns a proposed "
                "invoice object for the given client and milestone."
            ),
        ),
        scope_sentinel.as_tool(
            name="scope_sentinel",
            description=(
                "Delegate inbound-client-email / scope-creep checks here. Returns "
                "proposed change-order actions for requests outside the SOW."
            ),
        ),
    ]
