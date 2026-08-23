"""Tests for the Scope Creep Sentinel (deterministic core, no AWS needed)."""

from __future__ import annotations

import json
import os

from memory import schema
from agents import scope_sentinel

MODEL_ID = "anthropic.claude-3-5-sonnet-20241022-v2:0"


def _sow():
    return {
        "deliverables": ["Landing page", "Contact form", "Responsive breakpoints"],
        "hourly_rate_usd": 75.0,
        "included_revisions": 2,
        "out_of_scope_examples": ["Dark mode toggle", "CMS integration"],
    }


def _client():
    return {
        "client_id": "client_001",
        "name": "Northwind Traders",
        "email": "accounts@northwind.example.com",
        "sow_terms": json.dumps(_sow()),
        "billing_rate": 75.0,
        "payment_history": [],
        "tone_log": [],
    }


def _email(body, subject="Client request", sender="client@example.com"):
    return {
        "sender": sender,
        "subject": subject,
        "body": body,
        "received_at": "2026-08-20T09:00:00Z",
    }


def test_quick_tweak_triggers_change_order_draft(tmp_path, monkeypatch):
    monkeypatch.setenv("PDF_OUTPUT_DIR", str(tmp_path))

    actions = scope_sentinel.check_inbox(
        [_email("Hey, can you also add a dark mode toggle real quick?")], _client()
    )

    assert len(actions) == 1
    action = actions[0]
    assert action[schema.ACTION_TYPE] == "change_order"
    assert action[schema.DRAFTED_CONTENT].endswith(".pdf")
    assert os.path.isfile(action[schema.DRAFTED_CONTENT])
    assert "Dark mode toggle" in action[schema.AGENT_REASONING]
    assert "225.00" in action[schema.AGENT_REASONING]  # 3h * $75/hr


def test_in_scope_request_triggers_no_action(tmp_path, monkeypatch):
    monkeypatch.setenv("PDF_OUTPUT_DIR", str(tmp_path))

    actions = scope_sentinel.check_inbox(
        [_email("Can you add the contact form to the landing page?")], _client()
    )

    assert actions == []


def test_unlisted_request_is_treated_as_out_of_scope(tmp_path, monkeypatch):
    monkeypatch.setenv("PDF_OUTPUT_DIR", str(tmp_path))

    actions = scope_sentinel.check_inbox(
        [_email("Can you also add an analytics dashboard?")], _client()
    )

    assert len(actions) == 1
    assert actions[0][schema.ACTION_TYPE] == "change_order"


def test_agent_reasoning_is_human_readable(tmp_path, monkeypatch):
    monkeypatch.setenv("PDF_OUTPUT_DIR", str(tmp_path))

    actions = scope_sentinel.check_inbox(
        [_email("Please add a dark mode toggle")], _client()
    )

    reasoning = actions[0][schema.AGENT_REASONING]
    assert "not listed in the SOW scope" in reasoning
    assert "estimated" in reasoning
    assert "hours" in reasoning


def test_classify_request_directly():
    sow = _sow()
    assert scope_sentinel.classify_request("Can you add a contact form?", sow) == "in_scope"
    assert (
        scope_sentinel.classify_request("Add a dark mode toggle", sow) == "out_of_scope"
    )
    assert (
        scope_sentinel.classify_request("Can you add an analytics dashboard?", sow)
        == "out_of_scope"
    )


def test_scope_sentinel_agent_registers_tools():
    agent = scope_sentinel.build_scope_sentinel_agent(MODEL_ID)
    assert "read_recent_emails" in agent.tool_names
    assert "generate_change_order_pdf" in agent.tool_names
