"""Shared tool registration pattern for specialist sub-agents.

CashflowGuardian's specialist agents (Invoice & Dunning today, Scope Creep
Sentinel on Day 8-10) are exposed to the Orchestrator as Strands *tools* via
``Agent.as_tool()`` — the "agents-as-tools" pattern — never as inline function
calls or ``if/else`` routing in the Orchestrator.

Delegation behind ``as_tool()`` keeps the Orchestrator as the single auditable
point of control: every externally-visible action still flows through it, while
the specialist's own model does the domain reasoning. To add a new specialist,
return its ``as_tool()`` from :func:`build_sub_agent_tools`.
"""

from __future__ import annotations

from typing import Any


def build_sub_agent_tools(model: Any) -> list[Any]:
    """Build each specialist agent and wrap it as a Strands tool.

    ``model`` is passed straight through to each specialist (a ``Model`` instance
    or a Bedrock model-id string). The specialist import is local to avoid a
    circular import (``invoice_dunning`` imports ``agents.tools.pdf_tool``).
    """
    from agents.invoice_dunning import build_invoice_dunning_agent

    invoice_dunning = build_invoice_dunning_agent(model)
    return [
        invoice_dunning.as_tool(
            name="invoice_dunning",
            description=(
                "Delegate milestone-complete events here. Returns a proposed "
                "invoice object for the given client and milestone."
            ),
        ),
    ]
