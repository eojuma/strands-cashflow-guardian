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
    late = next(a for a in dunnings if a[schema.CLIENT_ID] == "client_late")
    late14 = next(a for a in dunnings if a[schema.CLIENT_ID] == "client_late14")
    assert late[schema.ESCALATION_TIER] == "day_3"
    assert late14[schema.ESCALATION_TIER] == "day_14"

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

    # 4. Edit Northwind's day_3 reminder -> the edited content is what gets sent
    #    and the reminder is recorded on the client's tone_log.
    edited = "Subject: Updated reminder\n\nPlease review invoice inv_nw_002."
    status, executed = _api(
        "POST",
        f"/actions/{late[schema.ACTION_ID]}/resolve",
        {"decision": "edited", "edited_content": edited},
    )
    assert status == 200
    assert executed[schema.ACTION_STATUS] == schema.STATUS_EXECUTED
    assert demo_db[-1]["body"] == edited
    tone_log = dynamo_client.get_client("client_late")[schema.TONE_LOG]
    assert len(tone_log) == 1
    assert tone_log[0]["escalation_tier"] == "day_3"
    assert tone_log[0]["invoice_id"] == "inv_nw_002"

    # 5. Reject Beta's day_14 reminder -> no send, nothing recorded.
    sent_before = len(demo_db)
    status, executed = _api(
        "POST",
        f"/actions/{late14[schema.ACTION_ID]}/resolve",
        {"decision": "rejected"},
    )
    assert status == 200
    assert executed[schema.ACTION_STATUS] == schema.STATUS_REJECTED
    assert len(demo_db) == sent_before
    assert len(dynamo_client.get_client("client_late14")[schema.TONE_LOG]) == 2  # unchanged

    # 6. Nothing pending remains; the activity log shows all three resolutions.
    status, remaining = _api("GET", "/actions/pending")
    assert status == 200
    assert remaining == []

    status, activity = _api("GET", "/activity-log")
    assert status == 200
    assert len(activity) == 3
    assert all(a[schema.AGENT_REASONING] for a in activity)

    # 7. A second scheduled pass must not re-propose what already went out:
    #    Northwind's day_3 is on the tone_log and Lumen's milestone is already
    #    invoiced, so only Beta's day_14 (rejected, never sent) is re-proposed.
    summary = orchestrator_handler.run_scheduled_check(today=TODAY.isoformat())
    assert summary["proposals_persisted"] == 1
    assert summary["by_type"] == {"dunning_email": 1}
    status, again = _api("GET", "/actions/pending")
    assert status == 200
    assert len(again) == 1
    assert again[0][schema.ESCALATION_TIER] == "day_14"
    assert again[0][schema.CLIENT_ID] == "client_late14"
