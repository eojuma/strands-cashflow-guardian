"""DynamoDB schema — the single source of truth for CashflowGuardian's memory.

Two tables back the whole system (see ``docs/ARCHITECTURE.md`` §4):

``Clients``
    One record per client relationship. Holds the statement of work (SOW),
    billing rate, payment history, and the tone/escalation log that prevents the
    dunning agent from re-sending the same reminder tier twice.

``PendingActions``
    Every externally-visible action an agent *proposes* (an invoice, a change
    order, a dunning email). Nothing is executed until its ``status`` moves to
    ``approved`` or ``edited`` — this table is the enforcement point for the
    human-in-the-loop invariant in §7.

``memory/dynamo_client.py`` imports these constants so a table name, key name, or
allowed value is never duplicated (and can never drift) across the codebase.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

# ---------------------------------------------------------------------------
# Table names (kept in sync with infra/template.yaml)
# ---------------------------------------------------------------------------
CLIENTS_TABLE = "CashflowGuardian-Clients"
PENDING_ACTIONS_TABLE = "CashflowGuardian-PendingActions"

# GSI on PendingActions: list a client's actions (dashboard Approvals panel).
PENDING_ACTIONS_BY_CLIENT_INDEX = "ClientIdIndex"

# ---------------------------------------------------------------------------
# Attribute names
# ---------------------------------------------------------------------------
# Clients
CLIENT_ID = "client_id"
NAME = "name"
EMAIL = "email"
SOW_TERMS = "sow_terms"              # String (JSON)
BILLING_RATE = "billing_rate"        # Number
PAYMENT_HISTORY = "payment_history"  # List<Map>
TONE_LOG = "tone_log"                # List<Map>
CREATED_AT = "created_at"            # ISO 8601
UPDATED_AT = "updated_at"            # ISO 8601

# PendingActions
ACTION_ID = "action_id"              # PK
# CLIENT_ID reused above (GSI key in PendingActions)
ACTION_TYPE = "action_type"
ESCALATION_TIER = "escalation_tier"  # day_3 / day_7 / day_14 / None
DRAFTED_CONTENT = "drafted_content"
AGENT_REASONING = "agent_reasoning"
ACTION_STATUS = "status"
ACTION_RESOLVED_AT = "resolved_at"   # ISO 8601 / None

# ---------------------------------------------------------------------------
# Allowed values (enforced by the validators below)
# ---------------------------------------------------------------------------
ACTION_TYPES = ("invoice", "change_order", "dunning_email")
ESCALATION_TIERS = ("day_3", "day_7", "day_14")
STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_EDITED = "edited"
STATUS_REJECTED = "rejected"
STATUS_EXECUTED = "executed"
ACTION_STATUSES = (
    STATUS_PENDING,
    STATUS_APPROVED,
    STATUS_EDITED,
    STATUS_REJECTED,
    STATUS_EXECUTED,
)

# SOW term keys (inside the ``sow_terms`` JSON string; see parse_sow_terms)
SOW_DELIVERABLES = "deliverables"
SOW_HOURLY_RATE_USD = "hourly_rate_usd"
SOW_INCLUDED_REVISIONS = "included_revisions"
SOW_OUT_OF_SCOPE_EXAMPLES = "out_of_scope_examples"


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------
def validate_action_type(value: Any) -> None:
    if value not in ACTION_TYPES:
        raise ValueError(f"unknown action_type {value!r}; expected one of {ACTION_TYPES}")


def validate_escalation_tier(value: Any) -> None:
    if value is not None and value not in ESCALATION_TIERS:
        raise ValueError(
            f"unknown escalation_tier {value!r}; expected one of {ESCALATION_TIERS} or None"
        )


def validate_action_status(value: Any) -> None:
    if value not in ACTION_STATUSES:
        raise ValueError(f"unknown status {value!r}; expected one of {ACTION_STATUSES}")


def validate_client(client: dict[str, Any]) -> None:
    """Validate a full client record before it is written."""
    required = (CLIENT_ID, NAME, EMAIL, SOW_TERMS, BILLING_RATE)
    missing = [f for f in required if client.get(f) in (None, "")]
    if missing:
        raise ValueError(f"client record is missing required field(s): {', '.join(missing)}")
    if not isinstance(client.get(BILLING_RATE), (int, float, Decimal)):
        raise ValueError("billing_rate must be numeric")
    if not isinstance(client.get(SOW_TERMS), str):
        raise ValueError("sow_terms must be a JSON string")
    # Validate it round-trips as JSON so a malformed SOW is caught at write time.
    json.loads(client[SOW_TERMS])


def validate_action(action: dict[str, Any]) -> None:
    """Validate a proposed action before it is written to ``PendingActions``."""
    required = (CLIENT_ID, ACTION_TYPE, DRAFTED_CONTENT, AGENT_REASONING)
    missing = [f for f in required if action.get(f) in (None, "")]
    if missing:
        raise ValueError(f"action record is missing required field(s): {', '.join(missing)}")
    validate_action_type(action[ACTION_TYPE])
    if action.get(ACTION_STATUS) is not None:
        validate_action_status(action[ACTION_STATUS])
    if action.get(ESCALATION_TIER) is not None:
        validate_escalation_tier(action[ESCALATION_TIER])


def parse_sow_terms(sow_terms: str) -> dict[str, Any]:
    """Parse a stored ``sow_terms`` JSON string into a queryable dict.

    ``sow_terms`` is stored as a JSON string in the ``Clients`` table; the Scope
    Creep Sentinel uses this to read deliverables and out-of-scope examples.
    """
    return json.loads(sow_terms or "{}")


# ---------------------------------------------------------------------------
# Table shape (consumed by memory/dynamo_client.create_tables() for local runs
# and tests; the SAM template mirrors this same shape in YAML).
# ---------------------------------------------------------------------------
CLIENTS_ATTR_DEFS = [{"AttributeName": CLIENT_ID, "AttributeType": "S"}]
CLIENTS_KEY_SCHEMA = [{"AttributeName": CLIENT_ID, "KeyType": "HASH"}]

PENDING_ACTIONS_ATTR_DEFS = [
    {"AttributeName": ACTION_ID, "AttributeType": "S"},
    {"AttributeName": CLIENT_ID, "AttributeType": "S"},
]
PENDING_ACTIONS_KEY_SCHEMA = [{"AttributeName": ACTION_ID, "KeyType": "HASH"}]
PENDING_ACTIONS_GSIS = [
    {
        "IndexName": PENDING_ACTIONS_BY_CLIENT_INDEX,
        "KeySchema": [{"AttributeName": CLIENT_ID, "KeyType": "HASH"}],
        "Projection": {"ProjectionType": "ALL"},
    }
]


# ---------------------------------------------------------------------------
# Documented example item (one fake client record)
# ---------------------------------------------------------------------------
_SOW_TERMS_DICT: dict[str, Any] = {
    SOW_DELIVERABLES: ["Landing page", "Contact form", "Responsive breakpoints"],
    SOW_HOURLY_RATE_USD: 75.0,
    SOW_INCLUDED_REVISIONS: 2,
    SOW_OUT_OF_SCOPE_EXAMPLES: ["Dark mode toggle", "CMS integration"],
}

EXAMPLE_CLIENT: dict[str, Any] = {
    CLIENT_ID: "client_001",
    NAME: "Northwind Traders",
    EMAIL: "accounts@northwind.example.com",
    SOW_TERMS: json.dumps(_SOW_TERMS_DICT),
    BILLING_RATE: Decimal("75.00"),
    PAYMENT_HISTORY: [
        {
            "invoice_id": "inv_001",
            "amount": Decimal("1200.00"),
            "due_date": "2026-08-01T00:00:00+00:00",
            "paid_date": "2026-08-03T00:00:00+00:00",
            "status": "paid",
        }
    ],
    TONE_LOG: [
        {
            "date": "2026-08-10T00:00:00+00:00",
            "escalation_tier": "day_3",
            "summary": "Friendly reminder sent for inv_002.",
        }
    ],
    CREATED_AT: "2026-08-01T00:00:00+00:00",
    UPDATED_AT: "2026-08-10T00:00:00+00:00",
}
