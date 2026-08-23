"""End-to-end (deterministic) integration across both specialists + the orchestrator.

No Bedrock is required: the specialists' deterministic cores (``check_due_dates``
and ``check_inbox``) feed the Orchestrator's human-in-the-loop state machine
(propose -> persist -> resolve -> execute), all in moto's in-memory DynamoDB.
"""

from __future__ import annotations

import json

import pytest
from moto import mock_aws

from agents import invoice_dunning, orchestrator, scope_sentinel
from memory import dynamo_client, schema


@pytest.fixture
def db(monkeypatch, tmp_path):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("PDF_OUTPUT_DIR", str(tmp_path))
    with mock_aws():
        dynamo_client.create_tables()
        yield


def _seed_client():
    return dynamo_client.put_client(
        {
            schema.CLIENT_ID: "client_001",
            schema.NAME: "Northwind Traders",
            schema.EMAIL: "accounts@northwind.example.com",
            schema.SOW_TERMS: json.dumps(
                {
                    "deliverables": ["Landing page", "Contact form"],
                    "hourly_rate_usd": 75.0,
                    "included_revisions": 2,
                    "out_of_scope_examples": ["Dark mode toggle"],
                }
            ),
            schema.BILLING_RATE: 75.0,
            schema.PAYMENT_HISTORY: [
                {
                    "invoice_id": "inv_002",
                    "amount": 1200.0,
                    "due_date": "2026-08-12T00:00:00+00:00",
                    "status": "unpaid",
                }
            ],
            schema.TONE_LOG: [],
        }
    )


def test_full_loop_propose_persist_resolve(db):
    client = _seed_client()
    today = "2026-08-20T00:00:00+00:00"

    # 1. Both specialists produce proposed actions (deterministic cores).
    dunning = invoice_dunning.check_due_dates(client, today)
    change_orders = scope_sentinel.check_inbox(
        [
            {
                "sender": "client@example.com",
                "subject": "quick tweak",
                "body": "Hey, can you add a dark mode toggle?",
                "received_at": today,
            }
        ],
        client,
    )
    proposed = dunning + change_orders
    assert len(proposed) == 2  # one dunning email + one change order

    # 2. The orchestrator persists them as pending (nothing executed).
    persisted = orchestrator.persist_proposed_actions(proposed)
    assert all(a[schema.ACTION_STATUS] == schema.STATUS_PENDING for a in persisted)

    # 3. Approve one -> executes and sends exactly once.
    calls = []

    def fake_send(**kwargs):
        calls.append(kwargs)

    resolved = orchestrator.resolve_action(
        persisted[0][schema.ACTION_ID], "approved", send_fn=fake_send
    )
    assert resolved[schema.ACTION_STATUS] == schema.STATUS_EXECUTED
    assert len(calls) == 1

    # 4. Reject the other -> no additional send.
    before = len(calls)
    rejected = orchestrator.resolve_action(
        persisted[1][schema.ACTION_ID], "rejected", send_fn=fake_send
    )
    assert rejected[schema.ACTION_STATUS] == schema.STATUS_REJECTED
    assert len(calls) == before
