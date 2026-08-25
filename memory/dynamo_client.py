"""Strands Memory <-> DynamoDB adapter.

Thin read/write layer over the two tables defined in ``memory/schema.py``. All
agents and Lambda handlers go through this module — never through ``boto3``
directly — so the schema stays the single source of truth.

Authentication uses the standard boto3 credential chain (``~/.aws/credentials``,
SSO, or environment variables). For local development against DynamoDB Local,
set ``DYNAMODB_ENDPOINT_URL`` (boto3's own ``AWS_ENDPOINT_URL`` also works).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Attr, Key

from memory import schema


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _coerce_numbers(value: Any) -> Any:
    """Recursively convert Python floats to Decimal (DynamoDB rejects floats)."""
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _coerce_numbers(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_coerce_numbers(v) for v in value]
    return value


def _omit_none(value: dict[str, Any]) -> dict[str, Any]:
    """Drop None values so optional attributes (``resolved_at``, ``escalation_tier``)
    are represented by absence rather than an explicit NULL."""
    return {k: v for k, v in value.items() if v is not None}


def _dynamodb():
    endpoint = os.getenv("DYNAMODB_ENDPOINT_URL")
    kwargs: dict[str, Any] = {"endpoint_url": endpoint} if endpoint else {}
    return boto3.resource("dynamodb", **kwargs)


def _table(name: str):
    return _dynamodb().Table(name)


# ---------------------------------------------------------------------------
# Provisioning (local runs + tests; production uses infra/template.yaml)
# ---------------------------------------------------------------------------
def create_tables() -> None:
    """Create both tables if they do not exist. Idempotent."""
    dynamodb = _dynamodb()
    existing = {t.name for t in dynamodb.tables.all()}

    if schema.CLIENTS_TABLE not in existing:
        dynamodb.create_table(
            TableName=schema.CLIENTS_TABLE,
            AttributeDefinitions=schema.CLIENTS_ATTR_DEFS,
            KeySchema=schema.CLIENTS_KEY_SCHEMA,
            BillingMode="PAY_PER_REQUEST",
        )
    if schema.PENDING_ACTIONS_TABLE not in existing:
        dynamodb.create_table(
            TableName=schema.PENDING_ACTIONS_TABLE,
            AttributeDefinitions=schema.PENDING_ACTIONS_ATTR_DEFS,
            KeySchema=schema.PENDING_ACTIONS_KEY_SCHEMA,
            GlobalSecondaryIndexes=schema.PENDING_ACTIONS_GSIS,
            BillingMode="PAY_PER_REQUEST",
        )


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------
def get_client(client_id: str) -> dict[str, Any] | None:
    """Return a client record, or ``None`` if it does not exist."""
    resp = _table(schema.CLIENTS_TABLE).get_item(Key={schema.CLIENT_ID: client_id})
    return resp.get("Item")


def get_clients() -> list[dict[str, Any]]:
    """List all client records for the dashboard."""
    return _paginate(_table(schema.CLIENTS_TABLE).scan, {})


def put_client(client: dict[str, Any]) -> dict[str, Any]:
    """Insert or fully replace a client record (used for seeding/demo data)."""
    schema.validate_client(client)
    item = dict(client)
    item.setdefault(schema.CREATED_AT, _now_iso())
    item[schema.UPDATED_AT] = item.get(schema.UPDATED_AT, _now_iso())
    item = _coerce_numbers(_omit_none(item))
    _table(schema.CLIENTS_TABLE).put_item(Item=item)
    return item


def update_client(client_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    """Merge ``updates`` into a client record and refresh ``updated_at``.

    ``client_id`` is immutable and must be supplied as the first argument, not in
    ``updates``.
    """
    if not updates:
        raise ValueError("updates must not be empty")
    if schema.CLIENT_ID in updates:
        raise ValueError("client_id is immutable; pass it as the first argument")

    updates = _coerce_numbers(_omit_none(dict(updates)))
    updates[schema.UPDATED_AT] = _now_iso()

    names: dict[str, str] = {}
    values: dict[str, Any] = {}
    set_parts: list[str] = []
    for i, (key, value) in enumerate(updates.items()):
        name_ph, value_ph = f"#n{i}", f":v{i}"
        names[name_ph] = key
        values[value_ph] = value
        set_parts.append(f"{name_ph} = {value_ph}")

    resp = _table(schema.CLIENTS_TABLE).update_item(
        Key={schema.CLIENT_ID: client_id},
        UpdateExpression="SET " + ", ".join(set_parts),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
        ReturnValues="ALL_NEW",
    )
    return resp["Attributes"]


# ---------------------------------------------------------------------------
# PendingActions
# ---------------------------------------------------------------------------
def get_pending_action(action_id: str) -> dict[str, Any] | None:
    """Return a single pending action, or ``None`` if it does not exist."""
    resp = _table(schema.PENDING_ACTIONS_TABLE).get_item(Key={schema.ACTION_ID: action_id})
    return resp.get("Item")


def get_pending_actions(
    status: str | None = None, client_id: str | None = None
) -> list[dict[str, Any]]:
    """List actions, optionally filtered by ``status`` and/or ``client_id``.

    When ``client_id`` is given the ``ClientIdIndex`` GSI is used; otherwise a
    full scan is used (fine for MVP table sizes).
    """
    if status is not None:
        schema.validate_action_status(status)
    filter_expr = Attr(schema.ACTION_STATUS).eq(status) if status is not None else None

    table = _table(schema.PENDING_ACTIONS_TABLE)
    if client_id is not None:
        kwargs: dict[str, Any] = {
            "IndexName": schema.PENDING_ACTIONS_BY_CLIENT_INDEX,
            "KeyConditionExpression": Key(schema.CLIENT_ID).eq(client_id),
        }
        if filter_expr is not None:
            kwargs["FilterExpression"] = filter_expr
        return _paginate(table.query, kwargs)

    kwargs = {"FilterExpression": filter_expr} if filter_expr is not None else {}
    return _paginate(table.scan, kwargs)


def _paginate(operation, kwargs: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    resp = operation(**kwargs)
    items.extend(resp.get("Items", []))
    while "LastEvaluatedKey" in resp:
        resp = operation(ExclusiveStartKey=resp["LastEvaluatedKey"], **kwargs)
        items.extend(resp.get("Items", []))
    return items


def create_pending_action(action: dict[str, Any]) -> dict[str, Any]:
    """Write a proposed action. Defaults ``status`` to ``pending`` and assigns
    ``action_id``/``created_at`` when absent."""
    schema.validate_action(action)
    item = dict(action)
    if not item.get(schema.ACTION_ID):
        item[schema.ACTION_ID] = str(uuid.uuid4())
    item.setdefault(schema.ACTION_STATUS, schema.STATUS_PENDING)
    item.setdefault(schema.CREATED_AT, _now_iso())
    item = _coerce_numbers(_omit_none(item))
    _table(schema.PENDING_ACTIONS_TABLE).put_item(Item=item)
    return item


def update_action_status(action_id: str, status: str) -> dict[str, Any]:
    """Transition an action's status. Sets ``resolved_at`` (once) on the first
    transition out of ``pending``."""
    schema.validate_action_status(status)
    table = _table(schema.PENDING_ACTIONS_TABLE)

    update_expr = "SET #s = :s"
    names: dict[str, str] = {"#s": schema.ACTION_STATUS}
    values: dict[str, Any] = {":s": status}
    if status != schema.STATUS_PENDING:
        update_expr += ", #r = if_not_exists(#r, :r)"
        names["#r"] = schema.ACTION_RESOLVED_AT
        values[":r"] = _now_iso()

    resp = table.update_item(
        Key={schema.ACTION_ID: action_id},
        UpdateExpression=update_expr,
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
        ReturnValues="ALL_NEW",
    )
    return resp["Attributes"]


def update_action_content(action_id: str, content: str) -> dict[str, Any]:
    """Replace the drafted content of an action (the dashboard's Edit path)."""
    if not isinstance(content, str):
        raise TypeError("content must be a string")
    resp = _table(schema.PENDING_ACTIONS_TABLE).update_item(
        Key={schema.ACTION_ID: action_id},
        UpdateExpression="SET #c = :c",
        ExpressionAttributeNames={"#c": schema.DRAFTED_CONTENT},
        ExpressionAttributeValues={":c": content},
        ReturnValues="ALL_NEW",
    )
    return resp["Attributes"]
