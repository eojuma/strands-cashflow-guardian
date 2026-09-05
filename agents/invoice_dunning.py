"""Invoice & Dunning specialist agent.

Exposed to the Orchestrator as a Strands *tool* via ``Agent.as_tool()`` (the
"agents-as-tools" pattern), never called directly by application code.

This module also owns the deterministic dunning escalation ladder (Days 6-7):
tier selection, late-fee calculation, and tone-safe drafting. The ladder is pure
Python — testable without Bedrock — and every email it produces is a *proposal*
for human approval, never an auto-send.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from strands import Agent

from memory import schema
from agents.tools.guardrails_config import apply_tone_guardrail
from agents.tools.pdf_tool import generate_change_order_pdf, generate_invoice_pdf

INVOICE_DUNNING_NAME = "Invoice & Dunning Agent"
INVOICE_DUNNING_DESCRIPTION = (
    "Generates an invoice the moment a milestone completes and runs the "
    "tone-controlled dunning escalation ladder."
)

INVOICE_DUNNING_SYSTEM_PROMPT = """\
You are the Invoice & Dunning specialist agent for CashflowGuardian.

Two responsibilities:

1. Invoicing — when a milestone completes, call the `generate_invoice_pdf` tool
   with the client_id, amount, and due_date, then report the file path back.

2. Dunning — for overdue invoices, draft the reminder at the right escalation
   tier (day_3 friendly check-in, day_7 formal notice, day_14 work-pause
   warning) and pass every draft through the `apply_tone_guardrail` tool so the
   tone stays professional. You only propose emails — a human approves before
   anything is sent, and the day_14 warning is never sent without approval.

Do not invent payment history and do not send anything externally yourself.
"""

# Escalation thresholds: days past due at which each tier applies.
TIER_THRESHOLDS = {"day_3": 3, "day_7": 7, "day_14": 14}
_TIERS_DESCENDING = ("day_14", "day_7", "day_3")

# Key used on proposed actions to make the human-in-the-loop invariant explicit.
REQUIRES_HUMAN_APPROVAL = "requires_human_approval"

# Default invoice payment term (net-14) used when a milestone completes.
INVOICE_TERM_DAYS = 14


def _parse_date(value: str):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


def days_overdue(due_date: str, today: str) -> int:
    """Whole days between ``due_date`` and ``today`` (0 if not yet overdue)."""
    delta = (_parse_date(today) - _parse_date(due_date)).days
    return max(0, delta)


def _tone_log_has_tier(tone_log: list[dict], tier: str, invoice_id: str) -> bool:
    """True if the given invoice already received a reminder at ``tier``."""
    for entry in tone_log or []:
        if entry.get("escalation_tier") != tier:
            continue
        if entry.get("invoice_id") == invoice_id:
            return True
        if invoice_id and invoice_id in (entry.get("summary") or ""):
            return True
    return False


def determine_next_tier(invoice: dict, tone_log: list[dict], today: str) -> str | None:
    """Return the next escalation tier for an invoice, or ``None``.

    Escalates to the highest applicable tier that has not already been sent for
    this invoice. Never downgrades: if the highest applicable tier was already
    sent, returns ``None`` and waits for the next threshold.
    """
    if invoice.get("status") == "paid":
        return None

    overdue = days_overdue(invoice.get("due_date", today), today)
    invoice_id = invoice.get("invoice_id", "")

    for tier in _TIERS_DESCENDING:
        if overdue >= TIER_THRESHOLDS[tier]:
            if _tone_log_has_tier(tone_log, tier, invoice_id):
                return None
            return tier
    return None


def calculate_late_fee(amount: float, billing_rate: float, tier: str) -> float:
    """Late fee for a tier: 0 at day_3, 5% at day_7, 10% at day_14 (min one
    billable hour)."""
    if tier == "day_3":
        return 0.0
    rate = 0.05 if tier == "day_7" else 0.10
    return round(max(float(billing_rate or 0.0), amount * rate), 2)


def draft_dunning_email(
    tier: str,
    client_name: str,
    invoice: dict,
    late_fee: float,
    billing_rate: float,
) -> str:
    """Draft a professional reminder for the given tier (deterministic)."""
    invoice_id = invoice.get("invoice_id", "")
    amount = float(invoice.get("amount", 0.0))
    due_date = invoice.get("due_date", "")

    if tier == "day_3":
        subject = f"Friendly reminder — invoice {invoice_id}"
        body = (
            f"Hi {client_name},\n\n"
            f"Just a friendly check-in on invoice {invoice_id} (${amount:,.2f}), "
            f"which was due {due_date}. No rush — could you let us know its status "
            f"when you get a chance?\n\nThank you,\nCashflowGuardian"
        )
    elif tier == "day_7":
        subject = f"Overdue invoice {invoice_id}"
        body = (
            f"Hi {client_name},\n\n"
            f"Invoice {invoice_id} (${amount:,.2f}) is now past due (due {due_date}). "
            f"A late fee of ${late_fee:,.2f} now applies.\n\n"
            f"Please arrange payment at your earliest convenience, or reach out if "
            f"anything looks incorrect.\n\nThank you,\nCashflowGuardian"
        )
    else:  # day_14
        subject = f"Final notice — invoice {invoice_id}"
        body = (
            f"Hi {client_name},\n\n"
            f"We have followed up twice on invoice {invoice_id} (${amount:,.2f}) "
            f"and it remains outstanding. We value the work we do together, but we "
            f"will need to pause further work until this is resolved.\n\n"
            f"Please reach out so we can sort this out together.\n\n"
            f"Thank you,\nCashflowGuardian"
        )
    return f"Subject: {subject}\n\n{body}"


def _reasoning(tier: str, invoice: dict, today: str) -> str:
    invoice_id = invoice.get("invoice_id", "")
    overdue = days_overdue(invoice.get("due_date", today), today)
    return (
        f"Invoice {invoice_id} is {overdue} days overdue; escalating to {tier} "
        f"reminder (proposed, never auto-sent)."
    )


def check_due_dates(client: dict, today: str) -> list[dict]:
    """Return proposed dunning actions for a client's overdue invoices.

    Pure and deterministic: reads ``payment_history`` and ``tone_log``, picks the
    next tier per unpaid invoice, drafts the email, applies the tone guardrail,
    and returns proposed-action dicts. Nothing is sent.
    """
    client_id = client.get(schema.CLIENT_ID, "")
    client_name = client.get(schema.NAME, client_id)
    billing_rate = float(client.get(schema.BILLING_RATE, 0.0) or 0.0)
    payment_history = client.get(schema.PAYMENT_HISTORY, []) or []
    tone_log = client.get(schema.TONE_LOG, []) or []

    proposed: list[dict] = []
    for invoice in payment_history:
        if invoice.get("status") == "paid":
            continue

        tier = determine_next_tier(invoice, tone_log, today)
        if tier is None:
            continue

        amount = float(invoice.get("amount", 0.0))
        late_fee = calculate_late_fee(amount, billing_rate, tier)
        draft = draft_dunning_email(tier, client_name, invoice, late_fee, billing_rate)
        draft = apply_tone_guardrail(draft, tier)

        proposed.append(
            {
                schema.CLIENT_ID: client_id,
                schema.ACTION_TYPE: "dunning_email",
                schema.ESCALATION_TIER: tier,
                "invoice_id": invoice.get("invoice_id", ""),
                schema.DRAFTED_CONTENT: draft,
                schema.AGENT_REASONING: _reasoning(tier, invoice, today),
                REQUIRES_HUMAN_APPROVAL: True,
            }
        )
    return proposed


def default_due_date(completed_at: str | None = None) -> str:
    """Invoice due date: ``INVOICE_TERM_DAYS`` after the milestone completion
    date (defaults to now when no completion date is given)."""
    base = _parse_datetime(completed_at) if completed_at else datetime.now(timezone.utc)
    return (base + timedelta(days=INVOICE_TERM_DAYS)).date().isoformat()


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def propose_invoice(
    client: dict,
    milestone: dict,
    today: str | None = None,
) -> dict:
    """Return a proposed ``invoice`` action for a completed milestone.

    Deterministic: drafts the invoice PDF via ``generate_invoice_pdf`` and
    attaches a human-readable ``agent_reasoning``. Nothing is sent; the returned
    record must be persisted as ``pending`` and approved by a human first.
    """
    client_id = client.get(schema.CLIENT_ID, "")
    client_name = client.get(schema.NAME, client_id)
    amount = float(milestone.get("amount", 0.0))
    name = milestone.get("name", milestone.get("milestone_id", "Milestone"))
    due_date = milestone.get("due_date") or default_due_date(milestone.get("completed_at"))

    pdf_path = generate_invoice_pdf(
        client_id, amount, due_date, client_name=client_name
    )

    return {
        schema.CLIENT_ID: client_id,
        schema.ACTION_TYPE: "invoice",
        schema.DRAFTED_CONTENT: pdf_path,
        # Structured fields mirror what the PDF shows so the dashboard (and a
        # later dunning pass) never needs to parse the document itself.
        "milestone_id": milestone.get("milestone_id"),
        "amount": amount,
        "due_date": due_date,
        "milestone_name": name,
        schema.AGENT_REASONING: (
            f"Milestone '{name}' completed; no invoice generated yet. "
            f"Proposed invoice for ${amount:,.2f} due {due_date} (PDF pending approval)."
        ),
        REQUIRES_HUMAN_APPROVAL: True,
    }


def check_milestones(client: dict) -> list[dict]:
    """Return proposed ``invoice`` actions for every completed, uninvoiced
    milestone on the client's record.

    Reads ``payment_history``/``milestones`` (as seeded by the milestone-complete
    trigger) and proposes an invoice for any milestone whose invoice has not yet
    been generated. Deterministic and pure — nothing is sent.
    """
    client_id = client.get(schema.CLIENT_ID, "")
    invoiced_ids = {
        entry.get("milestone_id")
        for entry in (client.get(schema.PAYMENT_HISTORY) or [])
        if entry.get("milestone_id")
    }
    proposed: list[dict] = []
    for milestone in client.get(schema.MILESTONES) or []:
        if milestone.get("status") != "complete":
            continue
        if milestone.get("milestone_id") in invoiced_ids:
            continue
        proposed.append(propose_invoice(client, milestone))
    return proposed


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
        tools=[generate_invoice_pdf, generate_change_order_pdf, apply_tone_guardrail],
    )
