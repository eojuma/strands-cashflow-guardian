"""Invoice & Dunning specialist agent.

Exposed to the Orchestrator as a Strands *tool* via ``Agent.as_tool()`` (the
"agents-as-tools" pattern), never called directly by application code.

Day 3 returned a fake invoice object. Day 4 wires in real PDF generation: the
agent now has the ``generate_invoice_pdf`` / ``generate_change_order_pdf`` tools
registered, so its reasoning loop invokes them instead of returning a stub.
"""

from __future__ import annotations

from typing import Any

from strands import Agent

from agents.tools.pdf_tool import generate_change_order_pdf, generate_invoice_pdf

INVOICE_DUNNING_NAME = "Invoice & Dunning Agent"
INVOICE_DUNNING_DESCRIPTION = (
    "Generates an invoice the moment a milestone completes and, later, runs the "
    "tone-controlled dunning escalation ladder."
)

INVOICE_DUNNING_SYSTEM_PROMPT = """\
You are the Invoice & Dunning specialist agent for CashflowGuardian.

You receive milestone-complete events (text containing a client_id, milestone
name, amount, and optionally a completion date). When a milestone completes:

1. Call the `generate_invoice_pdf` tool with the client_id, the amount, and a
   due_date (14 days after completion when given, otherwise today + 14 days).
2. Report back the exact file path the tool returned. That path is the proposed
   invoice a human must approve before anything is sent.

For out-of-scope work described in an event, call `generate_change_order_pdf`
with the client_id, the description, and the estimated extra hours.

Do not invent payment history and do not send anything externally (email arrives
on a later day).
"""


def build_invoice_dunning_agent(model: Any) -> Agent:
    """Build the Invoice & Dunning specialist agent for the given model.

    ``model`` may be a Strands ``Model`` instance or a Bedrock model-id string
    (the same values ``Agent`` accepts).
    """
    return Agent(
        name=INVOICE_DUNNING_NAME,
        description=INVOICE_DUNNING_DESCRIPTION,
        model=model,
        system_prompt=INVOICE_DUNNING_SYSTEM_PROMPT,
        tools=[generate_invoice_pdf, generate_change_order_pdf],
    )
