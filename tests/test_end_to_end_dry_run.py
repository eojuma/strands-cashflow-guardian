"""Day 18 dry run across seeding, scheduling, approval API, and activity log."""

from __future__ import annotations

import json
from datetime import date

import pytest
from moto import mock_aws

from lambda_handlers import api_handler, orchestrator_handler
from memory import dynamo_client, schema
from scripts.seed_demo_data import demo_clients


@pytest.fixture
def demo_db(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    with mock_aws():
        dynamo_client.create_tables()
        for client in demo_clients(date(2026, 8, 25)):
            dynamo_client.put_client(client)
        yield


def _api(method: str, path: str, payload=None, send_fn=None):
    event = {
        "rawPath": path,
        "requestContext": {"http": {"method": method}},
        "body": json.dumps(payload) if payload is not None else None,
    }
    response = api_handler.lambda_handler(event, None, send_fn=send_fn)
    return response["statusCode"], json.loads(response["body"])


def test_full_deployed_shape_dry_run(demo_db):
    # EventBridge sends no clients: the handler must load them from DynamoDB.
    scheduled = orchestrator_handler.lambda_handler(
        {"today": "2026-08-25"}, None
    )
    scheduled_body = json.loads(scheduled["body"])
    assert scheduled_body["count"] == 1
    assert scheduled_body["actions"][0][schema.ESCALATION_TIER] == "day_7"

    status, clients = _api("GET", "/clients")
    assert status == 200
    assert len(clients) == 3

    status, pending = _api("GET", "/actions/pending")
    assert status == 200
    assert len(pending) == 1

    sends = []
    action_id = pending[0][schema.ACTION_ID]
    status, executed = _api(
        "POST",
        f"/actions/{action_id}/resolve",
        {"decision": "edited", "edited_content": "Subject: Updated reminder\n\nPlease review invoice late_001."},
        send_fn=lambda **kwargs: sends.append(kwargs),
    )
    assert status == 200
    assert executed[schema.ACTION_STATUS] == schema.STATUS_EXECUTED
    assert sends[0]["body"].startswith("Subject: Updated reminder")

    status, activity = _api("GET", "/activity-log")
    assert status == 200
    assert len(activity) == 1
    assert activity[0][schema.AGENT_REASONING]
    assert _api("GET", "/actions/pending")[1] == []
