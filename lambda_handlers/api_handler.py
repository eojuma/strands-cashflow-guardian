"""Minimal REST API for the CashflowGuardian dashboard."""

from __future__ import annotations

import json
from decimal import Decimal

from agents import orchestrator
from memory import dynamo_client, schema


def _json_default(value):
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def _response(status: int, body) -> dict:
    return {
        "statusCode": status,
        "headers": {
            "content-type": "application/json",
            "access-control-allow-origin": "*",
            "access-control-allow-headers": "content-type",
            "access-control-allow-methods": "GET,POST,OPTIONS",
        },
        "body": json.dumps(body, default=_json_default),
    }


def _path(event: dict) -> str:
    return event.get("rawPath") or event.get("path") or "/"


def _method(event: dict) -> str:
    return (event.get("requestContext", {}).get("http", {}).get("method") or event.get("httpMethod") or "GET").upper()


def lambda_handler(event, context, send_fn=None):
    """Route API Gateway HTTP API or REST API events."""
    event = event or {}
    method, path = _method(event), _path(event).rstrip("/") or "/"
    if method == "OPTIONS":
        return _response(204, {})
    if method == "GET" and path == "/clients":
        return _response(200, dynamo_client.get_clients())
    if method == "GET" and path == "/actions/pending":
        return _response(200, dynamo_client.get_pending_actions(status=schema.STATUS_PENDING))
    if method == "GET" and path == "/activity-log":
        actions = [a for a in dynamo_client.get_pending_actions() if a.get(schema.ACTION_STATUS) != schema.STATUS_PENDING]
        actions.sort(key=lambda a: a.get(schema.ACTION_RESOLVED_AT, a.get(schema.CREATED_AT, "")), reverse=True)
        return _response(200, actions)
    prefix, suffix = "/actions/", "/resolve"
    if method == "POST" and path.startswith(prefix) and path.endswith(suffix):
        action_id = path[len(prefix):-len(suffix)].strip("/")
        try:
            payload = json.loads(event.get("body") or "{}")
        except json.JSONDecodeError:
            return _response(400, {"error": "Request body must be valid JSON"})
        decision = payload.get("decision")
        if decision not in {"approved", "edited", "rejected"}:
            return _response(400, {"error": "decision must be approved, edited, or rejected"})
        if decision == "edited" and not isinstance(payload.get("edited_content"), str):
            return _response(400, {"error": "edited_content is required for edited decisions"})
        action = orchestrator.resolve_action(action_id, decision, payload.get("edited_content"), send_fn=send_fn)
        return _response(200 if action else 404, action or {"error": "Action not found"})
    return _response(404, {"error": "Not found"})
