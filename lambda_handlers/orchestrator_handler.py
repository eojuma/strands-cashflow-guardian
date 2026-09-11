"""Scheduled EventBridge handler — the deterministic "run a scheduled check" path.

This is the Lambda entry point wired to the EventBridge rule in
``infra/template.yaml``. It runs a full pass of the *deterministic* checks the
specialists own against every client in memory, then persists everything as
``pending`` via the Orchestrator's human-in-the-loop state machine. Nothing is
executed or sent on this path — a human approves in the dashboard first.

Two checks run every scheduled pass:

- The dunning escalation ladder (``invoice_dunning.check_due_dates``) — an
  unpaid invoice that has crossed the day_3/day_7/day_14 threshold gets a
  proposed reminder.
- The Scope Creep Sentinel (``scope_sentinel.check_inbox``) — but only when
  Gmail is configured, since it needs to read the inbox; otherwise the scan is
  skipped and reported in the summary rather than failing the whole run.

Milestone-to-invoice proposals are raised here too: any milestone whose status is
``complete`` (seeded by ``scripts/seed_demo_data.py`` or the dashboard's
"mark milestone complete" action) gets an invoice proposed, persisted, and then
flipped to ``invoiced`` on the client record — so a milestone is never proposed
twice even though both the EventBridge rule and the dashboard's
"run scheduled check" button reach this same function.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from agents import invoice_dunning, orchestrator
from memory import dynamo_client, schema

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _gmail_configured() -> bool:
    """True when a Gmail OAuth token is available so the inbox can be read.

    Requires the *token*, not just the client secret: the interactive consent
    flow cannot run in Lambda, so a secret without a token must not be treated
    as usable (it would hang until the function times out).
    """
    from agents.tools.gmail_tool import gmail_available

    return gmail_available()


def run_scheduled_check(
    clients: list[dict] | None = None,
    today: str | None = None,
    scan_inbox: bool = False,
) -> dict[str, Any]:
    """Run one scheduled pass and persist every proposed action as ``pending``.

    Args:
        clients: Client records to check (defaults to all in DynamoDB).
        today: ISO timestamp used as "now" (injectable for tests).
        scan_inbox: when True, fetch recent inbox emails and run the Scope
            Sentinel against each client (requires Gmail OAuth configured).

    Returns:
        A summary dict: counts per action type persisted and any skipped checks.
    """
    from agents import scope_sentinel

    clients = clients if clients is not None else dynamo_client.list_clients()
    today = today or _now_iso()

    proposed: list[dict] = []
    summary = {"clients_checked": len(clients), "skipped_scope_scan": False}

    inbox_by_client: dict[str, list[dict]] = {}
    if scan_inbox:
        if not _gmail_configured():
            logger.warning("scan_inbox requested but Gmail is not configured — skipping")
            summary["skipped_scope_scan"] = True
            scan_inbox = False
        else:
            inbox_by_client = _group_inbox_by_client(today)

    for client in clients:
        proposed.extend(_propose_milestone_invoices(client))
        proposed.extend(invoice_dunning.check_due_dates(client, today))

        if scan_inbox:
            emails = inbox_by_client.get(client.get("client_id", ""), [])
            if emails:
                proposed.extend(scope_sentinel.check_inbox(emails, client))

    persisted = orchestrator.persist_proposed_actions(proposed)

    summary["proposals_persisted"] = len(persisted)
    summary["by_type"] = _count_by_type(persisted)
    return summary


def run_scope_scan(
    client_id: str | None = None,
    clients: list[dict] | None = None,
    today: str | None = None,
) -> dict[str, Any]:
    """Run only the Scope Creep Sentinel against a synthetic inbound email.

    A Gmail-free demo/test path: builds an out-of-scope request from the target
    client's own SOW and runs the same ``scope_sentinel.check_inbox`` core used
    by the scheduled path and the agent tool, persisting any change order as
    ``pending``. An existing pending change order for the target is not
    duplicated. The regular ``/run-scheduled-check`` path is untouched.
    """
    from agents import scope_sentinel

    clients = clients if clients is not None else dynamo_client.list_clients()
    today = today or _now_iso()
    targets = _select_scope_targets(clients, client_id)

    proposed: list[dict] = []
    for client in targets:
        cid = client.get(schema.CLIENT_ID, "")
        existing = (
            dynamo_client.get_pending_actions(status=schema.STATUS_PENDING, client_id=cid)
            if cid
            else []
        )
        if any(a.get(schema.ACTION_TYPE) == "change_order" for a in existing):
            continue
        email = scope_sentinel.demo_scope_email(client, today=today)
        if email:
            proposed.extend(scope_sentinel.check_inbox([email], client))

    persisted = orchestrator.persist_proposed_actions(proposed)
    return {
        "clients_checked": len(targets),
        "proposals_persisted": len(persisted),
        "by_type": _count_by_type(persisted),
    }


def _select_scope_targets(clients: list[dict], client_id: str | None) -> list[dict]:
    """Pick which client(s) the demo scope scan should check.

    An explicit ``client_id`` wins; otherwise prefer the seeded scope persona
    (id containing "scope"), then any client whose SOW lists out-of-scope
    examples, then the first client.
    """
    if client_id:
        return [c for c in clients if c.get(schema.CLIENT_ID) == client_id]

    preferred = next(
        (c for c in clients if "scope" in (c.get(schema.CLIENT_ID) or "")), None
    )
    if preferred:
        return [preferred]
    for client in clients:
        terms = schema.parse_sow_terms(client.get(schema.SOW_TERMS, "{}"))
        if terms.get(schema.SOW_OUT_OF_SCOPE_EXAMPLES):
            return [client]
    return clients[:1]


def _propose_milestone_invoices(client: dict) -> list[dict]:
    """Propose an invoice for every complete, uninvoiced milestone.

    Idempotent per milestone: once an invoice has been proposed and persisted,
    the milestone's status is flipped ``complete`` -> ``invoiced`` on the client
    record so a later run (or the dashboard's own trigger reaching this same
    helper) never proposes it twice.
    """
    proposals = invoice_dunning.check_milestones(client)
    if not proposals:
        return []

    client_id = client.get(schema.CLIENT_ID, "")
    milestones = list(client.get(schema.MILESTONES) or [])
    proposed_ids = {
        action.get("milestone_id") for action in proposals if action.get("milestone_id")
    }
    changed = False
    for milestone in milestones:
        if milestone.get("milestone_id") in proposed_ids and milestone.get("status") == "complete":
            milestone["status"] = "invoiced"
            changed = True
    if changed:
        dynamo_client.update_client(client_id, {schema.MILESTONES: milestones})

    return proposals


def _group_inbox_by_client(today: str) -> dict[str, list[dict]]:
    """Fetch recent emails once and group them by the client whose stored email
    address matches the sender. Emails with no matching client are dropped."""
    from agents.tools.gmail_tool import read_recent_emails

    since = today  # reuse the run timestamp; Gmail ignores the time-of-day part
    grouped: dict[str, list[dict]] = {}
    try:
        emails = read_recent_emails(since)
    except Exception as exc:  # noqa: BLE001 — a read failure must not kill the run
        logger.warning("inbox read failed (%s); scope scan skipped", exc)
        return grouped

    clients = dynamo_client.list_clients()
    for email in emails:
        sender = (email.get("sender") or "").lower()
        for client in clients:
            client_email = (client.get("email") or "").lower()
            if client_email and client_email in sender:
                grouped.setdefault(client.get("client_id", ""), []).append(email)
                break
    return grouped


def _count_by_type(actions: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for action in actions:
        key = action.get("action_type", "unknown")
        counts[key] = counts.get(key, 0) + 1
    return counts


def lambda_handler(event: dict | None = None, context: Any = None) -> dict[str, Any]:
    """AWS Lambda entry point for the scheduled (EventBridge) trigger.

    Accepts an optional JSON body override for local testing:
    ``{"scan_inbox": true}``.
    """
    event = event or {}
    body = event.get("body")
    try:
        params = json.loads(body) if body else {}
    except json.JSONDecodeError:
        params = {}

    summary = run_scheduled_check(scan_inbox=bool(params.get("scan_inbox", False)))
    logger.info("scheduled check complete: %s", summary)
    return summary
