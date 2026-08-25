"""Seed reproducible local/demo client records into DynamoDB."""

from __future__ import annotations

import json

from memory import dynamo_client, schema


def demo_clients() -> list[dict]:
    base = {schema.SOW_DELIVERABLES: ["Landing page", "Contact form"], schema.SOW_OUT_OF_SCOPE_EXAMPLES: ["Dark mode toggle", "CMS integration"], schema.SOW_INCLUDED_REVISIONS: 2}
    return [
        {schema.CLIENT_ID: "demo_on_time", schema.NAME: "On Time Co", schema.EMAIL: "on-time@example.com", schema.SOW_TERMS: json.dumps(base), schema.BILLING_RATE: 75.0, schema.PAYMENT_HISTORY: [{"invoice_id": "on_001", "amount": 900.0, "due_date": "2099-01-01T00:00:00+00:00", "status": "unpaid"}], schema.TONE_LOG: []},
        {schema.CLIENT_ID: "demo_late", schema.NAME: "Late Payer Ltd", schema.EMAIL: "late@example.com", schema.SOW_TERMS: json.dumps(base), schema.BILLING_RATE: 75.0, schema.PAYMENT_HISTORY: [{"invoice_id": "late_001", "amount": 1200.0, "due_date": "2026-08-01T00:00:00+00:00", "status": "unpaid"}], schema.TONE_LOG: []},
        {schema.CLIENT_ID: "demo_scope", schema.NAME: "Scope Creep Studio", schema.EMAIL: "scope@example.com", schema.SOW_TERMS: json.dumps(base), schema.BILLING_RATE: 85.0, schema.PAYMENT_HISTORY: [], schema.TONE_LOG: []},
    ]


def main() -> None:
    dynamo_client.create_tables()
    for client in demo_clients():
        dynamo_client.put_client(client)
    print(f"Seeded {len(demo_clients())} demo clients")


if __name__ == "__main__":
    main()
