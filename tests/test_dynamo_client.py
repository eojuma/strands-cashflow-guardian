"""Tests for the DynamoDB memory adapter.

Run against moto's in-memory DynamoDB, so no AWS credentials or deployed table
are required: the same code path (``boto3`` resource -> table operations) is
exercised, just against a mock backend.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from moto import mock_aws

from memory import dynamo_client
from memory import schema


@pytest.fixture
def db(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    with mock_aws():
        dynamo_client.create_tables()
        yield


def _client(**overrides):
    item = dict(schema.EXAMPLE_CLIENT)
    item.update(overrides)
    return item


def _action(**overrides):
    item = {
        schema.CLIENT_ID: "client_001",
        schema.ACTION_TYPE: "invoice",
        schema.DRAFTED_CONTENT: "Invoice #inv_002 for $1,200 due 2026-08-15",
        schema.AGENT_REASONING: "Milestone complete; no invoice generated yet.",
    }
    item.update(overrides)
    return item


def test_put_and_get_client_round_trip(db):
    dynamo_client.put_client(_client())
    got = dynamo_client.get_client("client_001")
    assert got is not None
    assert got[schema.NAME] == "Northwind Traders"
    assert got[schema.EMAIL] == "accounts@northwind.example.com"
    assert got[schema.BILLING_RATE] == Decimal("75.00")
    assert got[schema.PAYMENT_HISTORY][0]["invoice_id"] == "inv_001"


def test_get_missing_client_returns_none(db):
    assert dynamo_client.get_client("client_does_not_exist") is None


def test_update_client_merges_and_touches_updated_at(db):
    dynamo_client.put_client(_client())
    updated = dynamo_client.update_client("client_001", {schema.BILLING_RATE: 95.0})
    assert updated[schema.BILLING_RATE] == Decimal("95.0")
    assert updated[schema.UPDATED_AT] != schema.EXAMPLE_CLIENT[schema.UPDATED_AT]


def test_update_client_refuses_to_change_primary_key(db):
    dynamo_client.put_client(_client())
    with pytest.raises(ValueError):
        dynamo_client.update_client("client_001", {schema.CLIENT_ID: "client_002"})


def test_create_action_defaults_to_pending_and_assigns_id(db):
    action = dynamo_client.create_pending_action(_action())
    assert action[schema.ACTION_STATUS] == schema.STATUS_PENDING
    assert action[schema.ACTION_ID]
    assert action[schema.CREATED_AT]

    fetched = dynamo_client.get_pending_action(action[schema.ACTION_ID])
    assert fetched[schema.DRAFTED_CONTENT] == "Invoice #inv_002 for $1,200 due 2026-08-15"
    assert fetched[schema.AGENT_REASONING] == "Milestone complete; no invoice generated yet."


def test_list_pending_actions_filters_by_status(db):
    first = dynamo_client.create_pending_action(_action())
    dynamo_client.create_pending_action(
        _action(action_type="dunning_email", escalation_tier="day_3")
    )
    dynamo_client.update_action_status(first[schema.ACTION_ID], schema.STATUS_APPROVED)

    pending = dynamo_client.get_pending_actions(status=schema.STATUS_PENDING)
    assert len(pending) == 1
    assert pending[0][schema.ACTION_TYPE] == "dunning_email"


def test_list_pending_actions_by_client_via_gsi(db):
    dynamo_client.create_pending_action(_action())
    dynamo_client.create_pending_action(_action(client_id="client_002", action_type="change_order"))

    for_client = dynamo_client.get_pending_actions(client_id="client_002")
    assert len(for_client) == 1
    assert for_client[0][schema.ACTION_TYPE] == "change_order"


def test_update_action_status_sets_resolved_at_once(db):
    action = dynamo_client.create_pending_action(_action())
    action_id = action[schema.ACTION_ID]

    approved = dynamo_client.update_action_status(action_id, schema.STATUS_APPROVED)
    first_resolved_at = approved[schema.ACTION_RESOLVED_AT]
    assert first_resolved_at

    executed = dynamo_client.update_action_status(action_id, schema.STATUS_EXECUTED)
    assert executed[schema.ACTION_RESOLVED_AT] == first_resolved_at


def test_update_action_content_replaces_draft(db):
    action = dynamo_client.create_pending_action(_action())
    updated = dynamo_client.update_action_content(
        action[schema.ACTION_ID], "Edited invoice body."
    )
    assert updated[schema.DRAFTED_CONTENT] == "Edited invoice body."
    assert updated[schema.ACTION_STATUS] == schema.STATUS_PENDING


def test_invalid_action_type_is_rejected(db):
    with pytest.raises(ValueError):
        dynamo_client.create_pending_action(_action(action_type="wire_money"))
