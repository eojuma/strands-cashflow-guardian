"""Tests for the Orchestrator.

Two parts:

- Day 3 wiring — structural, no AWS (a Bedrock model-id *string* is used).
- Days 11-12 human-in-the-loop state machine — uses moto's in-memory DynamoDB
  and a fake ``send_fn``, so no credentials or network are required.
"""

from __future__ import annotations

import pytest
from moto import mock_aws
from strands import Agent

from agents import invoice_dunning, orchestrator
from agents.orchestrator import (
    FAKE_TRIGGER,
    ORCHESTRATOR_SYSTEM_PROMPT,
    build_orchestrator,
)
from agents.tools import build_sub_agent_tools
from memory import dynamo_client, schema

MODEL_ID = "anthropic.claude-3-5-sonnet-20241022-v2:0"


# --- Day 3: wiring ----------------------------------------------------------


def test_orchestrator_registers_both_specialists_as_tools():
    agent = build_orchestrator(model=MODEL_ID)
    assert isinstance(agent, Agent)
    assert "invoice_dunning" in agent.tool_names
    assert "scope_sentinel" in agent.tool_names


def test_sub_agents_are_exposed_as_agent_tools_not_functions():
    tools = build_sub_agent_tools(MODEL_ID)
    assert {t.tool_name for t in tools} == {"invoice_dunning", "scope_sentinel"}
    for tool in tools:
        # "agent" tool_type == agents-as-tools (Agent.as_tool()), not a plain @tool.
        assert tool.tool_type == "agent"


def test_orchestrator_system_prompt_instructs_routing():
    assert "invoice_dunning" in ORCHESTRATOR_SYSTEM_PROMPT
    assert "scope_sentinel" in ORCHESTRATOR_SYSTEM_PROMPT
    agent = build_orchestrator(model=MODEL_ID)
    assert "invoice_dunning" in agent.system_prompt
    assert "scope_sentinel" in agent.system_prompt


def test_invoice_dunning_prompt_instructs_pdf_generation():
    agent = invoice_dunning.build_invoice_dunning_agent(MODEL_ID)
    assert "milestone" in agent.system_prompt
    assert "generate_invoice_pdf" in agent.system_prompt


def test_fake_trigger_describes_a_milestone_complete_event():
    assert "milestone complete" in FAKE_TRIGGER
    assert "client_001" in FAKE_TRIGGER


# --- Days 11-12: human-in-the-loop state machine ----------------------------


@pytest.fixture
def db(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    with mock_aws():
        dynamo_client.create_tables()
        yield


def _seed_client():
    return dynamo_client.put_client(
        {
            schema.CLIENT_ID: "client_001",
            schema.NAME: "Northwind Traders",
            schema.EMAIL: "accounts@northwind.example.com",
            schema.SOW_TERMS: "{}",
            schema.BILLING_RATE: 75.0,
        }
    )


def _seed_action(**overrides):
    action = {
        schema.CLIENT_ID: "client_001",
        schema.ACTION_TYPE: "dunning_email",
        schema.DRAFTED_CONTENT: "Subject: Overdue invoice inv_002\n\nHi, please pay.",
        schema.AGENT_REASONING: "Invoice overdue.",
    }
    action.update(overrides)
    return dynamo_client.create_pending_action(action)


def _fake_send():
    calls = []

    def send(**kwargs):
        calls.append(kwargs)

    return send, calls


def test_execute_action_requires_approved_state(db):
    _seed_client()
    action = _seed_action()
    send, calls = _fake_send()

    assert orchestrator.execute_action(action[schema.ACTION_ID], send_fn=send) is False
    assert calls == []
    status = dynamo_client.get_pending_action(action[schema.ACTION_ID])[schema.ACTION_STATUS]
    assert status == schema.STATUS_PENDING


def test_approve_sends_and_marks_executed(db):
    _seed_client()
    action = _seed_action()
    send, calls = _fake_send()

    result = orchestrator.resolve_action(action[schema.ACTION_ID], "approved", send_fn=send)

    assert result[schema.ACTION_STATUS] == schema.STATUS_EXECUTED
    assert len(calls) == 1
    assert calls[0]["to"] == "accounts@northwind.example.com"
    assert calls[0]["body"] == action[schema.DRAFTED_CONTENT]


def test_edit_changes_what_gets_sent(db):
    _seed_client()
    action = _seed_action()
    send, calls = _fake_send()

    edited = "Subject: revised\n\nGentler wording."
    result = orchestrator.resolve_action(
        action[schema.ACTION_ID], "edited", edited_content=edited, send_fn=send
    )

    assert result[schema.ACTION_STATUS] == schema.STATUS_EXECUTED
    assert calls[0]["body"] == edited


def test_reject_halts_with_no_side_effects(db):
    _seed_client()
    action = _seed_action()
    send, calls = _fake_send()

    result = orchestrator.resolve_action(action[schema.ACTION_ID], "rejected", send_fn=send)

    assert result[schema.ACTION_STATUS] == schema.STATUS_REJECTED
    assert calls == []


def test_resolve_action_is_idempotent(db):
    _seed_client()
    action = _seed_action()
    send, calls = _fake_send()

    orchestrator.resolve_action(action[schema.ACTION_ID], "approved", send_fn=send)
    again = orchestrator.resolve_action(action[schema.ACTION_ID], "approved", send_fn=send)

    assert again[schema.ACTION_STATUS] == schema.STATUS_EXECUTED
    assert len(calls) == 1  # not executed twice


def test_persist_proposed_actions_sets_pending(db):
    proposed = [
        {
            schema.CLIENT_ID: "client_001",
            schema.ACTION_TYPE: "invoice",
            schema.DRAFTED_CONTENT: "invoice.pdf",
            schema.AGENT_REASONING: "milestone complete",
        }
    ]

    persisted = orchestrator.persist_proposed_actions(proposed)

    assert len(persisted) == 1
    assert persisted[0][schema.ACTION_STATUS] == schema.STATUS_PENDING
    assert persisted[0][schema.ACTION_ID]


def test_executing_approved_invoice_records_to_payment_history(db):
    _seed_client()
    action = _seed_action(
        action_type="invoice",
        amount=2400.0,
        due_date="2026-09-01",
        milestone_id="mvp",
    )
    send, calls = _fake_send()

    result = orchestrator.resolve_action(
        action[schema.ACTION_ID], "approved", send_fn=send
    )

    assert result[schema.ACTION_STATUS] == schema.STATUS_EXECUTED
    assert len(calls) == 1
    client = dynamo_client.get_client("client_001")
    history = client[schema.PAYMENT_HISTORY]
    assert len(history) == 1
    assert history[0]["status"] == "unpaid"
    assert history[0]["milestone_id"] == "mvp"
    assert history[0]["amount"] == 2400.0
