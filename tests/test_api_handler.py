from __future__ import annotations

import json

import pytest
from moto import mock_aws

from lambda_handlers import api_handler
from memory import dynamo_client, schema


@pytest.fixture
def db(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    with mock_aws():
        dynamo_client.create_tables()
        dynamo_client.put_client({schema.CLIENT_ID: "c1", schema.NAME: "Client", schema.EMAIL: "client@example.com", schema.SOW_TERMS: "{}", schema.BILLING_RATE: 75})
        yield


def event(method, path, body=None):
    return {"rawPath": path, "requestContext": {"http": {"method": method}}, "body": json.dumps(body) if body is not None else None}


def body(response):
    return json.loads(response["body"])


def test_lists_clients_and_pending_actions(db):
    dynamo_client.create_pending_action({schema.CLIENT_ID: "c1", schema.ACTION_TYPE: "dunning_email", schema.DRAFTED_CONTENT: "Reminder", schema.AGENT_REASONING: "Invoice overdue"})
    assert len(body(api_handler.lambda_handler(event("GET", "/clients"), None))) == 1
    assert len(body(api_handler.lambda_handler(event("GET", "/actions/pending"), None))) == 1


def test_approve_executes_and_moves_action_to_activity(db):
    action = dynamo_client.create_pending_action({schema.CLIENT_ID: "c1", schema.ACTION_TYPE: "dunning_email", schema.DRAFTED_CONTENT: "Reminder", schema.AGENT_REASONING: "Invoice overdue"})
    calls = []
    response = api_handler.lambda_handler(event("POST", f"/actions/{action[schema.ACTION_ID]}/resolve", {"decision": "approved"}), None, send_fn=lambda **kwargs: calls.append(kwargs))
    assert response["statusCode"] == 200
    assert body(response)[schema.ACTION_STATUS] == schema.STATUS_EXECUTED
    assert len(calls) == 1
    assert len(body(api_handler.lambda_handler(event("GET", "/activity-log"), None))) == 1


def test_reject_has_no_external_side_effect(db):
    action = dynamo_client.create_pending_action({schema.CLIENT_ID: "c1", schema.ACTION_TYPE: "change_order", schema.DRAFTED_CONTENT: "file.pdf", schema.AGENT_REASONING: "Outside SOW"})
    calls = []
    response = api_handler.lambda_handler(event("POST", f"/actions/{action[schema.ACTION_ID]}/resolve", {"decision": "rejected"}), None, send_fn=lambda **kwargs: calls.append(kwargs))
    assert body(response)[schema.ACTION_STATUS] == schema.STATUS_REJECTED
    assert calls == []
