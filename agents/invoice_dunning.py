"""Invoice & Dunning specialist agent — Day 3 stub.

Exposed to the Orchestrator as a Strands *tool* via ``Agent.as_tool()`` (the
"agents-as-tools" pattern), never called directly by application code. On a
milestone-complete event it returns a proposed invoice object. PDF generation
(Day 4) and Gmail send (Day 5) are wired in later.
"""

from __future__ import annotations

from typing import Any

from strands import Agent

INVOICE_DUNNING_NAME = "Invoice & Dunning Agent"
INVOICE_DUNNING_DESCRIPTION = (
    "Generates an invoice the moment a milestone completes and, later, runs the "
    "tone-controlled dunning escalation ladder. Day 3 stub: returns a proposed "
    "invoice object for a milestone-complete event — no PDF or email yet."
)

INVOICE_DUNNING_SYSTEM_PROMPT = """\
You are the Invoice & Dunning specialist agent for CashflowGuardian.

For now you receive exactly one kind of input: a milestone-complete event, which
arrives as text containing a client_id, a milestone name, and an amount.

Produce the proposed invoice object that will later become a real PDF and email.
Respond with ONLY a single JSON object (no markdown fences, no commentary), shaped
like:

{"client_id": "<id>", "milestone": "<name>", "amount": <number>, "due_date": "<ISO date>", "status": "proposed"}

Take the client_id, milestone, and amount from the input. Use a due_date 14 days
from the input's completion date when given, otherwise leave it as null. Do not
invent payment history and do not send anything externally.
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
    )
