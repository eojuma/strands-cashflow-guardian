"""Scheduled Lambda entry point for deterministic proposal persistence."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from agents import invoice_dunning, scope_sentinel
from agents import orchestrator
from memory import dynamo_client


def _event_date(event: dict) -> str:
    return event.get("today") or datetime.now(timezone.utc).isoformat()


def lambda_handler(event, context):
    """Process explicitly supplied demo events and persist proposals.

    Production callers should supply ``clients`` or ``client_ids`` resolved by
    the trigger layer. No external action is executed on this scheduled path.
    """
    event = event or {}
    proposals = []
    clients = event.get("clients")
    if clients is None:
        clients = dynamo_client.get_clients()
    for client in clients:
        proposals.extend(invoice_dunning.check_due_dates(client, _event_date(event)))
        proposals.extend(scope_sentinel.check_inbox(event.get("emails", {}).get(client.get("client_id"), []), client))
    persisted = orchestrator.persist_proposed_actions(proposals)
    return {"statusCode": 200, "body": json.dumps({"count": len(persisted), "actions": persisted}, default=str)}
