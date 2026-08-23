"""Scope Creep Sentinel specialist agent.

Compares inbound client emails against the stored Statement of Work (SOW) and
flags anything that is out of scope, estimating the extra billable hours and
drafting a change-order PDF.

The classification core is deterministic and testable (keyword match against the
SOW's ``deliverables`` vs ``out_of_scope_examples``). In the full system the LLM
refines this judgment, but the output contract — a proposed change-order action
with a human-readable ``agent_reasoning`` — is the same either way.
"""

from __future__ import annotations

import logging
from typing import Any

from strands import Agent

from memory import schema
from agents.tools.gmail_tool import read_recent_emails
from agents.tools.pdf_tool import generate_change_order_pdf

logger = logging.getLogger(__name__)

SCOPE_SENTINEL_NAME = "Scope Creep Sentinel"
SCOPE_SENTINEL_DESCRIPTION = (
    "Reads client emails, compares requests against the SOW, and drafts a "
    "change-order invoice when a request falls outside the agreed scope."
)

SCOPE_SENTINEL_SYSTEM_PROMPT = """\
You are the Scope Creep Sentinel for CashflowGuardian.

Read each client email and compare the request against the client's stored SOW.
When a request is out of scope, estimate the extra billable hours, draft a
change-order via the `generate_change_order_pdf` tool, and explain *why* it is
out of scope (that explanation must be visible, not just the final output).

You only propose change orders — a human reviews and approves before anything is
sent.
"""

IN_SCOPE = "in_scope"
OUT_OF_SCOPE = "out_of_scope"

DEFAULT_EXTRA_HOURS = 3.0

# Deterministic hour estimates for common out-of-scope requests (LLM-refinable).
EXTRA_HOURS_ESTIMATES = {
    "dark mode": 3.0,
    "cms": 8.0,
    "integration": 6.0,
    "payment": 6.0,
    "api": 5.0,
}


def _find_out_of_scope_item(email_body: str, sow_terms: dict) -> str | None:
    lowered = email_body.lower()
    for item in sow_terms.get(schema.SOW_OUT_OF_SCOPE_EXAMPLES, []):
        if str(item).lower() in lowered:
            return str(item)
    return None


def _find_in_scope_item(email_body: str, sow_terms: dict) -> str | None:
    lowered = email_body.lower()
    for item in sow_terms.get(schema.SOW_DELIVERABLES, []):
        if str(item).lower() in lowered:
            return str(item)
    return None


def classify_request(email_body: str, sow_terms: dict) -> str:
    """Return ``in_scope`` or ``out_of_scope`` for a request against a SOW.

    An explicit out-of-scope example wins; then an explicit deliverable is
    in-scope; anything unlisted is treated as scope creep (the safe default).
    """
    if _find_out_of_scope_item(email_body, sow_terms):
        return OUT_OF_SCOPE
    if _find_in_scope_item(email_body, sow_terms):
        return IN_SCOPE
    return OUT_OF_SCOPE


def estimate_extra_hours(request: str, sow_terms: dict) -> float:
    """Estimate extra billable hours for an out-of-scope request."""
    lowered = request.lower()
    for keyword, hours in EXTRA_HOURS_ESTIMATES.items():
        if keyword in lowered:
            return hours
    return DEFAULT_EXTRA_HOURS


def _request_description(email: dict, sow_terms: dict) -> str:
    body = email.get("body", "")
    item = _find_out_of_scope_item(body, sow_terms)
    if item:
        return item
    subject = (email.get("subject") or "").strip()
    if subject:
        return subject
    first_line = body.strip().splitlines()[0] if body.strip() else ""
    return first_line[:80] or "Unspecified request"


def build_agent_reasoning(
    description: str, extra_hours: float, billing_rate: float, sow_terms: dict
) -> str:
    """A human-readable explanation of why a request was flagged out of scope."""
    deliverables = ", ".join(sow_terms.get(schema.SOW_DELIVERABLES, [])) or "none listed"
    amount = extra_hours * billing_rate
    return (
        f"'{description}' is not listed in the SOW scope (deliverables: {deliverables}); "
        f"estimated {extra_hours:g} hours at ${billing_rate:.2f}/hr = ${amount:,.2f} change order."
    )


def check_inbox(emails: list[dict], client: dict) -> list[dict]:
    """Return proposed change-order actions for out-of-scope inbound emails.

    Pure and deterministic: classifies each email against the client's SOW,
    drafts a change-order PDF for anything out of scope, and attaches a
    human-readable ``agent_reasoning``. Nothing is sent.
    """
    sow_terms = schema.parse_sow_terms(client.get(schema.SOW_TERMS, "{}"))
    client_id = client.get(schema.CLIENT_ID, "")
    client_name = client.get(schema.NAME, client_id)
    billing_rate = float(client.get(schema.BILLING_RATE, 0.0) or 0.0)

    proposed: list[dict] = []
    for email in emails:
        body = email.get("body", "")
        if classify_request(body, sow_terms) == IN_SCOPE:
            logger.info("in-scope request (%s) -> no action", email.get("subject"))
            continue

        description = _request_description(email, sow_terms)
        extra_hours = estimate_extra_hours(body, sow_terms)
        reasoning = build_agent_reasoning(description, extra_hours, billing_rate, sow_terms)

        pdf_path = generate_change_order_pdf(
            client_id, description, extra_hours, client_name=client_name
        )
        logger.info("out-of-scope request -> change order: %s", reasoning)

        proposed.append(
            {
                schema.CLIENT_ID: client_id,
                schema.ACTION_TYPE: "change_order",
                schema.DRAFTED_CONTENT: pdf_path,
                schema.AGENT_REASONING: reasoning,
            }
        )
    return proposed


def build_scope_sentinel_agent(model: Any) -> Agent:
    """Build the Scope Creep Sentinel specialist agent for the given model."""
    return Agent(
        name=SCOPE_SENTINEL_NAME,
        description=SCOPE_SENTINEL_DESCRIPTION,
        model=model,
        system_prompt=SCOPE_SENTINEL_SYSTEM_PROMPT,
        tools=[read_recent_emails, generate_change_order_pdf],
    )
