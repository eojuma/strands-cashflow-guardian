"""Seed demo data: 3–5 synthetic client relationships.

Creates the DynamoDB tables if missing, then writes the personas the demo and
README reference:

- ``client_on_time``  — pays every invoice within days (no actions expected).
- ``client_late``     — one invoice 6 days overdue (day_3 check-in proposed).
- ``client_late14``   — one invoice 20 days overdue (day_14 final notice).
- ``client_scope``    — a milestone just completed (invoice proposal pending).
- ``client_clean``    — healthy relationship, nothing due (empty-state demo).

Scope-creep (change-order) scenarios are driven by inbound client email through
the Scope Creep Sentinel rather than by seeded records; the persona SOWs all
carry ``out_of_scope_examples`` so the classification logic has something to
match against when a demo email arrives.

Usage (against deployed tables):

    python scripts/seed_demo_data.py            # uses real AWS (boto3 chain)
    python scripts/seed_demo_data.py --reset    # overwrite existing records

For local development against DynamoDB Local set DYNAMODB_ENDPOINT_URL first.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memory import dynamo_client, schema

_RATE = 75.0

_SOW = {
    schema.SOW_DELIVERABLES: ["Landing page", "Contact form", "Responsive breakpoints"],
    schema.SOW_HOURLY_RATE_USD: _RATE,
    schema.SOW_INCLUDED_REVISIONS: 2,
    schema.SOW_OUT_OF_SCOPE_EXAMPLES: ["Dark mode toggle", "CMS integration"],
}


def _iso(days_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def _base(client_id: str, name: str, email: str) -> dict:
    return {
        schema.CLIENT_ID: client_id,
        schema.NAME: name,
        schema.EMAIL: email,
        schema.SOW_TERMS: json.dumps(_SOW),
        schema.BILLING_RATE: _RATE,
        schema.PAYMENT_HISTORY: [],
        schema.TONE_LOG: [],
        schema.MILESTONES: [],
        schema.CREATED_AT: _iso(60),
    }


def _build_personas() -> list[dict]:
    on_time = _base("client_on_time", "Acme Goodpay", "accounts@acmegoodpay.example.com")
    on_time[schema.PAYMENT_HISTORY] = [
        {
            "invoice_id": "inv_acme_001",
            "milestone_id": "brand_site",
            "amount": 1500.0,
            "due_date": _iso(20),
            "paid_date": _iso(17),
            "status": "paid",
        }
    ]

    late = _base("client_late", "Northwind Traders", "accounts@northwind.example.com")
    late[schema.PAYMENT_HISTORY] = [
        {
            "invoice_id": "inv_nw_002",
            "amount": 1200.0,
            "due_date": _iso(6),
            "status": "unpaid",
        }
    ]

    late14 = _base("client_late14", "Beta Analytics", "finance@betaanalytics.example.com")
    late14[schema.PAYMENT_HISTORY] = [
        {
            "invoice_id": "inv_ba_003",
            "amount": 3200.0,
            "due_date": _iso(20),
            "status": "unpaid",
        }
    ]
    late14[schema.TONE_LOG] = [
        {"date": _iso(17), "escalation_tier": "day_3", "summary": "Friendly reminder for inv_ba_003."},
        {"date": _iso(13), "escalation_tier": "day_7", "summary": "Overdue notice for inv_ba_003."},
    ]

    # Milestone just completed — the next scheduled check proposes its invoice.
    scope = _base("client_scope", "Lumen & Co", "hello@lumenco.example.com")
    scope[schema.MILESTONES] = [
        {
            "milestone_id": "mvp_launch",
            "name": "MVP launch",
            "amount": 2400.0,
            "status": "complete",
            "completed_at": _iso(3),
        }
    ]

    clean = _base("client_clean", "Fern Studio", "billing@fernstudio.example.com")

    return [on_time, late, late14, scope, clean]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="overwrite existing records")
    args = parser.parse_args()

    dynamo_client.create_tables()
    personas = _build_personas()

    for persona in personas:
        existing = dynamo_client.get_client(persona[schema.CLIENT_ID])
        if existing and not args.reset:
            print(f"skip  {persona[schema.CLIENT_ID]} (exists; use --reset to overwrite)")
            continue
        dynamo_client.put_client(persona)
        print(f"seed  {persona[schema.CLIENT_ID]}  {persona[schema.NAME]}")

    print(f"\nSeeded {len(personas)} persona(s). Run the scheduled check or open the dashboard.")


if __name__ == "__main__":
    main()
