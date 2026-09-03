"""Tests for the Lambda handlers: orchestrator scheduled check + REST API.

Both run against moto's in-memory DynamoDB with no AWS, Bedrock, or Gmail
credentials. The orchestrator scheduled check is fully deterministic; the REST
API exercises the full propose -> pending -> resolve -> execute -> activity log
loop with ``CASHFLOW_SEND_MODE=log`` so nothing leaves the process.
"""

from __future__ import annotations

import json

import pytest
from moto import mock_aws

from memory import dynamo_client, schema
from agents import orchestrator


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


def _client(**overrides):
    item = {
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
        schema.PAYMENT_HISTORY: [],
        schema.TONE_LOG: [],
        schema.MILESTONES: [],
    }
    item.update(overrides)
    return item


def _late_payer_client():
    item = _client()
    item[schema.PAYMENT_HISTORY] = [
        {
            "invoice_id": "inv_002",
            "amount": 1200.0,
            "due_date": "2026-08-12T00:00:00+00:00",
            "status": "unpaid",
        }
    ]
    return item


# --- orchestrator_handler ---------------------------------------------------


def test_run_scheduled_check_persists_dunning_proposal(db, monkeypatch):
    from lambda_handlers import orchestrator_handler

    dynamo_client.put_client(_late_payer_client())

    summary = orchestrator_handler.run_scheduled_check(today="2026-08-20T00:00:00+00:00")

    assert summary["clients_checked"] == 1
    assert summary["proposals_persisted"] == 1
    assert summary["by_type"] == {"dunning_email": 1}
    pending = dynamo_client.get_pending_actions(status=schema.STATUS_PENDING)
    assert pending[0][schema.ACTION_TYPE] == "dunning_email"


def test_scheduled_check_proposes_invoice_once_for_completed_milestone(db, monkeypatch, tmp_path):
    from lambda_handlers import orchestrator_handler

    client = _client()
    client[schema.MILESTONES] = [
        {
            "milestone_id": "mvp",
            "name": "MVP launch",
            "amount": 2400.0,
            "status": "complete",
            "completed_at": "2026-08-17T00:00:00+00:00",
        }
    ]
    dynamo_client.put_client(client)

    first = orchestrator_handler.run_scheduled_check(today="2026-08-20T00:00:00+00:00")
    second = orchestrator_handler.run_scheduled_check(today="2026-08-20T00:00:00+00:00")

    assert first["by_type"] == {"invoice": 1}
    # milestone flipped to invoiced -> never proposed twice
    assert second["by_type"] == {}
    pending = dynamo_client.get_pending_actions(status=schema.STATUS_PENDING)
    assert len(pending) == 1


def test_run_scheduled_check_skips_scope_scan_without_gmail(db):
    from lambda_handlers import orchestrator_handler

    dynamo_client.put_client(_client())
    summary = orchestrator_handler.run_scheduled_check(
        today="2026-08-20T00:00:00+00:00", scan_inbox=True
    )
    assert summary["skipped_scope_scan"] is True


def test_run_scheduled_check_reports_scope_proposals(db, monkeypatch):
    from lambda_handlers import orchestrator_handler

    monkeypatch.setenv("GMAIL_TOKEN_FILE", "/tmp/token.json")
    dynamo_client.put_client(_client())

    emails = [
        {
            "sender": "client@example.com <accounts@northwind.example.com>",
            "subject": "quick tweak",
            "body": "Can you add a dark mode toggle?",
            "received_at": "2026-08-20T09:00:00Z",
        }
    ]
    monkeypatch.setattr(
        "lambda_handlers.orchestrator_handler._group_inbox_by_client",
        lambda today: {"client_001": emails},
    )
    summary = orchestrator_handler.run_scheduled_check(
        today="2026-08-20T00:00:00+00:00", scan_inbox=True
    )
    assert summary["proposals_persisted"] == 1
    assert summary["by_type"] == {"change_order": 1}


# --- api_handler ------------------------------------------------------------


def test_list_clients_returns_summary(db):
    from lambda_handlers import api_handler

    dynamo_client.put_client(_client())
    resp = api_handler.route("GET", "/clients")
    assert resp["statusCode"] == 200
    clients = json.loads(resp["body"])
    assert clients[0][schema.CLIENT_ID] == "client_001"


def test_milestone_complete_proposes_pending_invoice(db):
    from lambda_handlers import api_handler

    dynamo_client.put_client(_client())
    resp = api_handler.route(
        "POST", "/clients/client_001/milestone-complete",
        {"name": "Landing page", "amount": 1200.0},
    )
    assert resp["statusCode"] == 200
    action = json.loads(resp["body"])
    assert action[schema.ACTION_TYPE] == "invoice"
    assert action[schema.ACTION_STATUS] == schema.STATUS_PENDING


def test_milestone_complete_is_idempotent(db):
    from lambda_handlers import api_handler

    dynamo_client.put_client(_client())
    api_handler.route(
        "POST", "/clients/client_001/milestone-complete",
        {"name": "Landing page", "amount": 1200.0},
    )
    second = api_handler.route(
        "POST", "/clients/client_001/milestone-complete",
        {"name": "Landing page", "amount": 1200.0},
    )
    assert json.loads(second["body"])["note"] == "milestone already recorded"
    pending = dynamo_client.get_pending_actions(status=schema.STATUS_PENDING)
    assert len(pending) == 1  # not duplicated


def test_resolve_approve_executes_and_logs_activity(db, monkeypatch):
    from lambda_handlers import api_handler

    monkeypatch.setenv("CASHFLOW_SEND_MODE", "log")
    dynamo_client.put_client(_client())
    created = api_handler.route(
        "POST", "/clients/client_001/milestone-complete",
        {"name": "Landing page", "amount": 1200.0},
    )
    action_id = json.loads(created["body"])[schema.ACTION_ID]

    resp = api_handler.route(
        "POST", f"/actions/{action_id}/resolve", {"decision": "approved"}
    )
    assert json.loads(resp["body"])[schema.ACTION_STATUS] == schema.STATUS_EXECUTED

    log = api_handler.route("GET", "/activity-log")
    entries = json.loads(log["body"])
    assert len(entries) == 1
    assert entries[0]["client_name"] == "Northwind Traders"


def test_resolve_reject_halts_without_activity(db):
    from lambda_handlers import api_handler

    dynamo_client.put_client(_client())
    created = api_handler.route(
        "POST", "/clients/client_001/milestone-complete",
        {"name": "Landing page", "amount": 1200.0},
    )
    action_id = json.loads(created["body"])[schema.ACTION_ID]

    resp = api_handler.route(
        "POST", f"/actions/{action_id}/resolve", {"decision": "rejected"}
    )
    assert json.loads(resp["body"])[schema.ACTION_STATUS] == schema.STATUS_REJECTED

    log = api_handler.route("GET", "/activity-log")
    entries = json.loads(log["body"])
    assert len(entries) == 1
    assert entries[0][schema.ACTION_STATUS] == schema.STATUS_REJECTED


def test_resolve_requires_known_decision(db):
    from lambda_handlers import api_handler

    dynamo_client.put_client(_client())
    created = api_handler.route(
        "POST", "/clients/client_001/milestone-complete",
        {"name": "Landing page", "amount": 1200.0},
    )
    action_id = json.loads(created["body"])[schema.ACTION_ID]
    resp = api_handler.route(
        "POST", f"/actions/{action_id}/resolve", {"decision": "maybe"}
    )
    assert resp["statusCode"] == 400


def test_unknown_route_returns_404(db):
    from lambda_handlers import api_handler

    assert api_handler.route("GET", "/nothing")["statusCode"] == 404


def test_lambda_handler_adapts_api_gateway_event(db, monkeypatch):
    from lambda_handlers import api_handler

    monkeypatch.setenv("CASHFLOW_SEND_MODE", "log")
    dynamo_client.put_client(_client())
    event = {"httpMethod": "GET", "path": "/clients", "body": None}
    resp = api_handler.lambda_handler(event)
    assert resp["statusCode"] == 200


def test_lambda_handler_accepts_http_api_v2_payload(db, monkeypatch):
    """SAM HttpApi sends v2 payloads (rawPath + requestContext.http.method)."""
    from lambda_handlers import api_handler

    monkeypatch.setenv("CASHFLOW_SEND_MODE", "log")
    dynamo_client.put_client(_client())
    event = {
        "version": "2.0",
        "routeKey": "ANY /{proxy+}",
        "rawPath": "/clients",
        "requestContext": {"http": {"method": "GET"}},
    }
    resp = api_handler.lambda_handler(event)
    assert resp["statusCode"] == 200
