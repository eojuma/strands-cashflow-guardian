"""REST surface for the Command Center dashboard (docs/ARCHITECTURE.md §9).

A single API Gateway / Lambda Function URL handler exposes the minimal REST
contract the dashboard needs. It is deliberately stateless and thin: every
endpoint maps onto the Orchestrator's deterministic state machine or the memory
layer — there is no agent logic here.

Endpoints
---------
GET  /clients                          List clients with summary status.
GET  /actions/pending                  List pending actions (Approvals panel).
POST /actions/{action_id}/resolve      Approve / edit / reject a pending action.
GET  /activity-log                     Recent resolved actions + agent_reasoning.
POST /clients/{client_id}/milestone-complete
                                       Manual milestone trigger -> proposed invoice.

Response shape: ``{"statusCode": int, "headers": {...}, "body": str}`` so the
function works as an API Gateway proxy handler directly.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from agents import orchestrator
from agents.tools.gmail_tool import send_email as _gmail_send_email
from memory import dynamo_client, schema

logger = logging.getLogger(__name__)

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


def _ok(payload: Any, status: int = 200) -> dict[str, Any]:
    return {"statusCode": status, "headers": CORS_HEADERS, "body": json.dumps(payload)}


def _err(message: str, status: int = 400) -> dict[str, Any]:
    return _ok({"error": message}, status)


def _send_fn():
    """Default email executor for approvals.

    Honors ``CASHFLOW_SEND_MODE=log`` (used for demos/dry runs without Gmail
    credentials): instead of sending, logs the message and returns True.
    """
    if os.getenv("CASHFLOW_SEND_MODE", "").lower() == "log":
        def log_send(to: str, subject: str, body: str) -> bool:
            logger.info("[dry-run send] to=%s subject=%s body=%s", to, subject, body)
            return True

        return log_send
    return _gmail_send_email


def _serialize(value: Any) -> Any:
    """Make DynamoDB-decoded values JSON-safe (Decimal -> float)."""
    from decimal import Decimal

    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize(v) for v in value]
    return value


def _client_summary(client: dict) -> dict[str, Any]:
    """Flatten a client record into the dashboard's summary view."""
    history = client.get(schema.PAYMENT_HISTORY) or []
    outstanding = sum(
        float(h.get("amount", 0.0)) for h in history if h.get("status") != "paid"
    )
    milestones = client.get(schema.MILESTONES) or []
    complete_milestones = sum(
        1 for m in milestones if m.get("status") == "complete"
    )
    return {
        schema.CLIENT_ID: client.get(schema.CLIENT_ID),
        schema.NAME: client.get(schema.NAME),
        schema.EMAIL: client.get(schema.EMAIL),
        schema.BILLING_RATE: float(client.get(schema.BILLING_RATE, 0.0) or 0.0),
        "outstanding_balance": round(outstanding, 2),
        "open_invoices": sum(1 for h in history if h.get("status") != "paid"),
        # Milestones completed but not yet invoiced = unbilled work on the books.
        "uninvoiced_milestones": complete_milestones,
        schema.UPDATED_AT: client.get(schema.UPDATED_AT),
    }


def _list_clients() -> dict[str, Any]:
    clients = dynamo_client.list_clients()
    return _ok([_client_summary(c) for c in clients])


def _list_pending() -> dict[str, Any]:
    actions = dynamo_client.get_pending_actions(status=schema.STATUS_PENDING)
    enriched = [_enrich_action(a) for a in actions]
    return _ok(enriched)


def _activity_log() -> dict[str, Any]:
    resolved_statuses = {
        schema.STATUS_APPROVED,
        schema.STATUS_EDITED,
        schema.STATUS_REJECTED,
        schema.STATUS_EXECUTED,
    }
    actions = [
        a for a in dynamo_client.list_actions() if a.get(schema.ACTION_STATUS) in resolved_statuses
    ]
    actions.sort(key=lambda a: a.get(schema.ACTION_RESOLVED_AT) or a.get(schema.CREATED_AT) or "", reverse=True)
    return _ok([_enrich_action(a) for a in actions[:100]])


def _enrich_action(action: dict) -> dict[str, Any]:
    """Attach the client name (for display) to an action record."""
    enriched = dict(action)
    client = dynamo_client.get_client(action.get(schema.CLIENT_ID, ""))
    enriched["client_name"] = (client or {}).get(schema.NAME, "")
    return _serialize(enriched)


def _resolve(action_id: str, body: dict) -> dict[str, Any]:
    decision = body.get("decision")
    if decision not in ("approved", "edited", "rejected"):
        return _err("decision must be one of: approved, edited, rejected")

    edited = body.get("edited_content")
    if decision == "edited" and not edited:
        return _err("edited_content is required when decision is 'edited'")

    result = orchestrator.resolve_action(action_id, decision, edited, send_fn=_send_fn())
    if result is None:
        return _err("action not found", 404)
    return _ok(_enrich_action(result))


def _run_scheduled_check(body: dict) -> dict[str, Any]:
    """Manually trigger the same deterministic checks the EventBridge rule runs.

    Exposed so the dashboard can offer a "Run check now" button instead of
    waiting up to 15 minutes for the next scheduled invocation. Bodies may pass
    ``{"scan_inbox": true}`` to include the Scope Creep Sentinel (requires Gmail).
    """
    from lambda_handlers import orchestrator_handler

    summary = orchestrator_handler.run_scheduled_check(
        scan_inbox=bool(body.get("scan_inbox", False))
    )
    return _ok(summary)


def _milestone_complete(client_id: str, body: dict) -> dict[str, Any]:
    """Record a completed milestone and propose its invoice.

    Writes the milestone onto the client record (status=complete) and proposes an
    invoice action so the Approvals panel surfaces it on the next refresh. Uses
    the same idempotent helper as the scheduled check, so the milestone is never
    invoiced twice.
    """
    name = (body.get("name") or "").strip()
    amount = body.get("amount")
    if not name:
        return _err("milestone 'name' is required")
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return _err("milestone 'amount' must be a number")

    client = dynamo_client.get_client(client_id)
    if client is None:
        return _err("client not found", 404)

    milestone_id = name.lower().replace(" ", "_")
    milestones = list(client.get(schema.MILESTONES) or [])
    if any(m.get("milestone_id") == milestone_id for m in milestones):
        return _ok({"client_id": client_id, "note": "milestone already recorded"})

    milestone = {
        "milestone_id": milestone_id,
        "name": name,
        "amount": amount,
        "status": "complete",
        "completed_at": body.get("completed_at"),
    }
    milestones.append(milestone)
    dynamo_client.update_client(client_id, {schema.MILESTONES: milestones})

    refreshed = dynamo_client.get_client(client_id)
    from lambda_handlers import orchestrator_handler

    proposals = orchestrator_handler._propose_milestone_invoices(refreshed)
    action = dynamo_client.create_pending_action(proposals[-1]) if proposals else None
    if action is None:
        return _ok({"client_id": client_id, "note": "milestone recorded"})
    return _ok(_enrich_action(action))


def route(method: str, path: str, body: dict | None = None) -> dict[str, Any]:
    """Dispatch a REST-style request to the matching handler (testable, no AWS).

    Args:
        method: HTTP method (upper-case).
        path: e.g. ``/clients``, ``/actions/{id}/resolve``.
        body: parsed JSON body for POSTs.
    """
    parts = [p for p in path.split("/") if p]

    if method == "GET" and parts == ["clients"]:
        return _list_clients()
    if method == "GET" and parts == ["actions", "pending"]:
        return _list_pending()
    if method == "GET" and parts == ["activity-log"]:
        return _activity_log()
    if method == "POST" and parts == ["run-scheduled-check"]:
        return _run_scheduled_check(body or {})
    if method == "POST" and len(parts) == 3 and parts[0] == "clients" and parts[2] == "milestone-complete":
        return _milestone_complete(parts[1], body or {})
    if method == "POST" and len(parts) == 3 and parts[0] == "actions" and parts[2] == "resolve":
        return _resolve(parts[1], body or {})

    return _err(f"no route for {method} {path}", 404)


def lambda_handler(event: dict | None = None, context: Any = None) -> dict[str, Any]:
    """API Gateway proxy handler — works with both REST (v1) and HTTP (v2)
    payloads, plus Lambda Function URLs (also v2-shaped)."""
    event = event or {}
    http_ctx = (event.get("requestContext") or {}).get("http") or {}

    method = (
        event.get("httpMethod")
        or http_ctx.get("method")
        or (event.get("routeKey") or "").split(" ")[0]
        or "GET"
    ).upper()
    # v1 keeps the path in 'path'; v2 and Function URLs in 'rawPath'.
    path = event.get("path") or event.get("rawPath") or "/"
    # Our route() parses the full path string, so pathParameters need not apply.

    if method == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    raw_body = event.get("body") or "{}"
    try:
        body = json.loads(raw_body)
    except json.JSONDecodeError:
        body = {}

    return route(method, path, body)
