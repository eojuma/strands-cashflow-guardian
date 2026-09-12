"""Reset CashflowGuardian to a clean, scripted demo state.

Writes to DynamoDB **directly** (no Lambda invocations, no emails sent).

What it does
------------
1. Deletes *all* PendingActions rows (this clears the Activity Log too, which is
   just the resolved subset of that table).
2. Resets the six demo clients' milestones / payment_history / tone_log to the
   scripted baseline (names, emails, SOW and rate are preserved), except
   ``client_demo`` which is set up per the demo spec.
3. Inserts exactly four pending proposals (invoice generation + day_3 + day_7 +
   day_14), each with a unique action_id, the proposing agent, a tier-appropriate
   email body, and a timestamp from today.

Idempotent: safe to run repeatedly. Targets real AWS by default; honours
``DYNAMODB_ENDPOINT_URL`` (e.g. DynamoDB Local) when set.

Usage:
    python scripts/reset_demo_state.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

from agents.invoice_dunning import calculate_late_fee, draft_dunning_email
from agents.tools.guardrails_config import apply_tone_guardrail
from memory import dynamo_client, schema

J = schema  # shorthand


def _dates() -> dict[str, str]:
    today = datetime.now(timezone.utc).date()

    def ago(n: int) -> str:
        return (today - timedelta(days=n)).isoformat()

    def ahead(n: int) -> str:
        return (today + timedelta(days=n)).isoformat()

    return {"today": today.isoformat(), "ago": ago, "ahead": ahead}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# 1. Wipe PendingActions (clears the pending queue *and* the Activity Log)
# ---------------------------------------------------------------------------
def clear_pending_actions() -> int:
    table = dynamo_client._table(schema.PENDING_ACTIONS_TABLE)
    deleted = 0
    kwargs: dict = {}
    while True:
        resp = table.scan(**kwargs)
        items = resp.get("Items", [])
        with table.batch_writer() as batch:
            for item in items:
                batch.delete_item(Key={schema.ACTION_ID: item[schema.ACTION_ID]})
                deleted += 1
        if "LastEvaluatedKey" not in resp:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    return deleted


# ---------------------------------------------------------------------------
# 2. Reset clients
# ---------------------------------------------------------------------------
def reset_clients(d: dict) -> None:
    ago, ahead = d["ago"], d["ahead"]

    # on-time payer: one paid invoice, nothing overdue.
    dynamo_client.update_client(
        "client_on_time",
        {
            schema.PAYMENT_HISTORY: [
                {
                    "invoice_id": "inv_acme_001",
                    "milestone_id": "brand_site",
                    "amount": 1500.0,
                    "due_date": ago(20),
                    "paid_date": ago(17),
                    "status": "paid",
                }
            ],
            schema.TONE_LOG: [],
            schema.MILESTONES: [],
        },
    )

    # 3 days overdue -> day_3
    dynamo_client.update_client(
        "client_late",
        {
            schema.PAYMENT_HISTORY: [
                {
                    "invoice_id": "inv_nw_002",
                    "amount": 1200.0,
                    "due_date": ago(3),
                    "status": "unpaid",
                }
            ],
            schema.TONE_LOG: [],
            schema.MILESTONES: [],
        },
    )

    # 7 days overdue -> day_7
    dynamo_client.update_client(
        "client_late14",
        {
            schema.PAYMENT_HISTORY: [
                {
                    "invoice_id": "inv_ba_003",
                    "amount": 3200.0,
                    "due_date": ago(7),
                    "status": "unpaid",
                }
            ],
            schema.TONE_LOG: [],
            schema.MILESTONES: [],
        },
    )

    # scope-creep client: clean slate (the Sentinel proposes during the demo).
    dynamo_client.update_client(
        "client_scope",
        {schema.PAYMENT_HISTORY: [], schema.TONE_LOG: [], schema.MILESTONES: []},
    )

    # healthy client with a just-completed milestone -> invoice proposal.
    dynamo_client.update_client(
        "client_clean",
        {
            schema.PAYMENT_HISTORY: [],
            schema.TONE_LOG: [],
            schema.MILESTONES: [
                {
                    "milestone_id": "api_integration",
                    "name": "API Integration",
                    "amount": 2200.0,
                    "status": "complete",
                    "completed_at": ago(0),
                }
            ],
        },
    )

    # the featured demo client: consulting engagement, milestone 1 overdue.
    import json

    consulting_sow = {
        "engagement": "Consulting engagement",
        "total_value_usd": 4500,
        "deliverables": ["Discovery & Audit", "Implementation", "Handover"],
        "milestones": ["Discovery & Audit", "Implementation", "Handover"],
        "hourly_rate_usd": 150,
        "included_revisions": 1,
        "out_of_scope_examples": ["Additional training", "Extended support"],
    }
    dynamo_client.update_client(
        "client_demo",
        {
            schema.NAME: "Juma Consultancy Ltd",
            schema.EMAIL: "evansodhiambo658@gmail.com",
            schema.SOW_TERMS: json.dumps(consulting_sow),
            schema.BILLING_RATE: 150.0,
            "dunning_tier": "day_14",
            schema.PAYMENT_HISTORY: [
                {
                    "invoice_id": "inv_jc_001",
                    "milestone_id": "discovery_audit",
                    "amount": 1500.0,
                    "due_date": ago(16),
                    "status": "unpaid",
                }
            ],
            schema.TONE_LOG: [],
            schema.MILESTONES: [
                {
                    "milestone_id": "discovery_audit",
                    "name": "Discovery & Audit",
                    "amount": 1500.0,
                    "status": "invoiced",
                    "completed_at": ago(30),
                },
                {
                    "milestone_id": "implementation",
                    "name": "Implementation",
                    "amount": 1500.0,
                    "status": "pending",
                },
                {
                    "milestone_id": "handover",
                    "name": "Handover",
                    "amount": 1500.0,
                    "status": "pending",
                },
            ],
        },
    )


# ---------------------------------------------------------------------------
# 3. Insert the four scripted pending proposals
# ---------------------------------------------------------------------------
def _dunning_body(tier: str, client_name: str, invoice: dict, billing_rate: float) -> str:
    late_fee = calculate_late_fee(float(invoice["amount"]), billing_rate, tier)
    return apply_tone_guardrail(
        draft_dunning_email(tier, client_name, invoice, late_fee, billing_rate), tier
    )


def seed_pending_actions(d: dict) -> list[dict]:
    ago, ahead = d["ago"], d["ahead"]
    now = _now()
    actions: list[dict] = []

    # (a) invoice generation — Fern Studio, milestone just completed.
    actions.append(
        {
            schema.CLIENT_ID: "client_clean",
            schema.ACTION_TYPE: "invoice",
            "agent": "Invoice Agent",
            schema.DRAFTED_CONTENT: "generated/invoice_client_clean_api_integration.pdf",
            schema.AGENT_REASONING: (
                "Milestone 'API Integration' marked complete; generating invoice for "
                "$2,200, due in 14 days."
            ),
            schema.ACTION_STATUS: schema.STATUS_PENDING,
            "amount": 2200.0,
            "due_date": ahead(14),
            "milestone_id": "api_integration",
            "milestone_name": "API Integration",
            "requires_human_approval": True,
            schema.CREATED_AT: now,
        }
    )

    # (b) day_3 friendly — Northwind Traders, 3 days overdue.
    nw_invoice = {"invoice_id": "inv_nw_002", "amount": 1200.0, "due_date": ago(3)}
    actions.append(
        {
            schema.CLIENT_ID: "client_late",
            schema.ACTION_TYPE: "dunning_email",
            "agent": "Dunning Agent",
            schema.ESCALATION_TIER: "day_3",
            "invoice_id": "inv_nw_002",
            schema.DRAFTED_CONTENT: _dunning_body("day_3", "Northwind Traders", nw_invoice, 75.0),
            schema.AGENT_REASONING: (
                "Invoice is 3 days overdue; sending day_3 friendly reminder "
                "(proposed, never auto-sent)."
            ),
            schema.ACTION_STATUS: schema.STATUS_PENDING,
            "requires_human_approval": True,
            schema.CREATED_AT: now,
        }
    )

    # (c) day_7 firm — Beta Analytics, 7 days overdue.
    ba_invoice = {"invoice_id": "inv_ba_003", "amount": 3200.0, "due_date": ago(7)}
    actions.append(
        {
            schema.CLIENT_ID: "client_late14",
            schema.ACTION_TYPE: "dunning_email",
            "agent": "Dunning Agent",
            schema.ESCALATION_TIER: "day_7",
            "invoice_id": "inv_ba_003",
            schema.DRAFTED_CONTENT: _dunning_body("day_7", "Beta Analytics", ba_invoice, 75.0),
            schema.AGENT_REASONING: (
                "Invoice is 7 days overdue; escalating to day_7 firm reminder "
                "(proposed, never auto-sent)."
            ),
            schema.ACTION_STATUS: schema.STATUS_PENDING,
            "requires_human_approval": True,
            schema.CREATED_AT: now,
        }
    )

    # (d) day_14 final notice — Juma Consultancy Ltd, 16 days overdue.
    final_body = (
        "Subject: Final notice — invoice inv_jc_001\n\n"
        "Hi Juma Consultancy Ltd,\n\n"
        "Invoice inv_jc_001 ($1,500.00) is now 16 days past due. This is a final "
        "notice: please arrange payment, or reply if anything looks incorrect, so "
        "we can avoid pausing work on the engagement.\n\n"
        "Thank you,\nCashflowGuardian"
    )
    actions.append(
        {
            schema.CLIENT_ID: "client_demo",
            schema.ACTION_TYPE: "dunning_email",
            "agent": "Dunning Agent",
            schema.ESCALATION_TIER: "day_14",
            "invoice_id": "inv_jc_001",
            schema.DRAFTED_CONTENT: apply_tone_guardrail(final_body, "day_14"),
            schema.AGENT_REASONING: (
                "Invoice inv_jc_001 is 16 days overdue; escalating to day_14 final "
                "notice (proposed, never auto-sent). Client has no prior payment "
                "history with us."
            ),
            schema.ACTION_STATUS: schema.STATUS_PENDING,
            "requires_human_approval": True,
            schema.CREATED_AT: now,
        }
    )

    return [dynamo_client.create_pending_action(a) for a in actions]


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def report() -> None:
    print("\n=== CLIENTS ===")
    for client in sorted(dynamo_client.list_clients(), key=lambda c: c[schema.CLIENT_ID]):
        cid = client[schema.CLIENT_ID]
        milestones = client.get(schema.MILESTONES) or []
        invoices = client.get(schema.PAYMENT_HISTORY) or []
        tone = client.get(schema.TONE_LOG) or []
        print(f"\n{cid}  {client.get(schema.NAME)}  <{client.get(schema.EMAIL)}>")
        print(f"  milestones: {[(m.get('name'), m.get('status')) for m in milestones] or 'none'}")
        print(f"  invoices:   {[(i.get('invoice_id'), i.get('status'), i.get('due_date')) for i in invoices] or 'none'}")
        print(f"  tone_log:   {[(t.get('escalation_tier'), t.get('invoice_id')) for t in tone] or 'none'}")

    print("\n=== PENDING ACTIONS ===")
    pending = sorted(
        dynamo_client.get_pending_actions(status=schema.STATUS_PENDING),
        key=lambda a: (a.get(schema.CLIENT_ID, ""), a.get(schema.ACTION_TYPE, "")),
    )
    print(f"count: {len(pending)}")
    for a in pending:
        print(
            f"  {a[schema.ACTION_ID][:8]}  {a.get('agent','?'):14}  "
            f"{a[schema.ACTION_TYPE]:14}  tier={a.get(schema.ESCALATION_TIER) or '-':6}  "
            f"client={a[schema.CLIENT_ID]}"
        )
        print(f"      why: {a.get(schema.AGENT_REASONING)}")


def main() -> None:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    d = _dates()

    deleted = clear_pending_actions()
    print(f"cleared {deleted} PendingActions rows (pending + activity log)")

    reset_clients(d)
    print("reset 6 clients")

    created = seed_pending_actions(d)
    print(f"seeded {len(created)} pending actions")

    report()


if __name__ == "__main__":
    main()
