"""Seed reproducible client personas used by the product demo."""

from __future__ import annotations

import json
from datetime import date, timedelta

from memory import dynamo_client, schema


def demo_clients(today: date | None = None) -> list[dict]:
    today = today or date.today()
    sow = {schema.SOW_DELIVERABLES: ["Landing page", "Contact form"], schema.SOW_OUT_OF_SCOPE_EXAMPLES: ["Dark mode toggle", "CMS integration"], schema.SOW_INCLUDED_REVISIONS: 2}
    return [
        {schema.CLIENT_ID: "demo_on_time", schema.NAME: "On Time Co", schema.EMAIL: "on-time@example.com", schema.SOW_TERMS: json.dumps(sow), schema.BILLING_RATE: 75.0, schema.PAYMENT_HISTORY: [{"invoice_id": "on_001", "amount": 900.0, "due_date": (today - timedelta(days=2)).isoformat(), "paid_date": (today - timedelta(days=4)).isoformat(), "status": "paid"}], schema.TONE_LOG: []},
        {schema.CLIENT_ID: "demo_late", schema.NAME: "Late Payer Ltd", schema.EMAIL: "late@example.com", schema.SOW_TERMS: json.dumps(sow), schema.BILLING_RATE: 75.0, schema.PAYMENT_HISTORY: [{"invoice_id": "late_001", "amount": 1200.0, "due_date": (today - timedelta(days=8)).isoformat(), "status": "unpaid"}], schema.TONE_LOG: []},
        {schema.CLIENT_ID: "demo_scope", schema.NAME: "Scope Creep Studio", schema.EMAIL: "scope@example.com", schema.SOW_TERMS: json.dumps(sow), schema.BILLING_RATE: 85.0, schema.PAYMENT_HISTORY: [], schema.TONE_LOG: []},
    ]


def demo_scope_email(today: date | None = None) -> dict:
    today = today or date.today()
    return {"sender": "scope@example.com", "subject": "One quick addition", "body": "Could you add a dark mode toggle as well?", "received_at": today.isoformat()}


def main() -> None:
    clients = demo_clients()
    dynamo_client.create_tables()
    for client in clients:
        dynamo_client.put_client(client)
    print(f"Seeded {len(clients)} demo clients: on-time, overdue, and scope-creep personas")


if __name__ == "__main__":
    main()
