"""Full end-to-end dry run across seeding, scheduling, approval API, and activity log.

Walks the deterministic path a deployed stack would take: seed personas ->
EventBridge scheduled check persists proposals -> the dashboard REST API
approves (invoice), edits (dunning email), and rejects (dunning email) them ->
the activity log reflects the resolved actions and the approved invoice lands in
payment history.
"""

from __future__ import annotations

import json
from datetime import date

import pytest
from moto import mock_aws

from lambda_handlers import api_handler, orchestrator_handler
from memory import dynamo_client, schema
from scripts.seed_demo_data import demo_clients


TODAY = date(2026, 8, 25)


@pytest.fixture
def demo_db(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")

    sends: list[dict] = []

    def fake_send(to, subject, body):
        sends.append({"to": to, "subject": subject, "body": body})
        return True

    monkeypatch.setattr(api_handler, "_gmail_send_email", fake_send)

    with mock_aws():
        dynamo_client.create_tables()
        for client in demo_clients(TODAY):
            dynamo_client.put_client(client)
        yield sends


def _api(method: str, path: str, payload=None):
    event = {
        "rawPath": path,
        "requestContext": {"http": {"method": method}},
        "body": json.dumps(payload) if payload is not None else None,
    }
    response = api_handler.lambda_handler(event, None)
    return response["statusCode"], json.loads(response["body"])


def test_full_deployed_shape_dry_run(demo_db):
    # 1. EventBridge passes no clients: the scheduled check loads them itself and
    #    persists exactly the expected proposals (2 dunning + 1 milestone invoice).
    summary = orchestrator_handler.run_scheduled_check(today=TODAY.isoformat())
    assert summary["clients_checked"] == 5
    assert summary["proposals_persisted"] == 3
    assert summary["by_type"] == {"dunning_email": 2, "invoice": 1}

    # Proposing an invoice flips the milestone to invoiced so it is never
    # proposed twice.
    scope_client = dynamo_client.get_client("client_scope")
    assert scope_client[schema.MILESTONES][0]["status"] == "invoiced"

    # 2. Dashboard REST API sees all clients and the pending proposals.
    status, clients = _api("GET", "/clients")
    assert status == 200
    assert len(clients) == 5

    status, pending = _api("GET", "/actions/pending")
    assert status == 200
    assert len(pending) == 3
    invoices = [a for a in pending if a[schema.ACTION_TYPE] == "invoice"]
    dunnings = [a for a in pending if a[schema.ACTION_TYPE] == "dunning_email"]
    assert len(invoices) == 1 and len(dunnings) == 2

    # 3. Approve the milestone invoice -> executed + recorded in payment history.
    status, executed = _api(
        "POST", f"/actions/{invoices[0][schema.ACTION_ID]}/resolve", {"decision": "approved"}
    )
    assert status == 200
    assert executed[schema.ACTION_STATUS] == schema.STATUS_EXECUTED
    history = dynamo_client.get_client("client_scope")[schema.PAYMENT_HISTORY]
    assert len(history) == 1
    assert history[0]["invoice_id"] == invoices[0][schema.ACTION_ID]
    assert history[0]["amount"] == 2400.0
    assert history[0]["status"] == "unpaid"

    # 4. Edit a dunning email -> the edited content is what gets "sent".
    edited = "Subject: Updated reminder\n\nPlease review invoice inv_nw_002."
    status, executed = _api(
        "POST",
        f"/actions/{dunnings[0][schema.ACTION_ID]}/resolve",
        {"decision": "edited", "edited_content": edited},
    )
    assert status == 200
    assert executed[schema.ACTION_STATUS] == schema.STATUS_EXECUTED
    assert demo_db[-1]["body"] == edited

    # 5. Reject the other dunning email -> no side effect.
    sent_before = len(demo_db)
    status, executed = _api(
        "POST", f"/actions/{dunnings[1][schema.ACTION_ID]}/resolve", {"decision": "rejected"}
    )
    assert status == 200
    assert executed[schema.ACTION_STATUS] == schema.STATUS_REJECTED
    assert len(demo_db) == sent_before

    # 6. Nothing pending remains; the activity log shows all three resolutions.
    status, remaining = _api("GET", "/actions/pending")
    assert status == 200
    assert remaining == []

    status, activity = _api("GET", "/activity-log")
    assert status == 200
    assert len(activity) == 3
    assert all(a[schema.AGENT_REASONING] for a in activity)
