"""Tests for the Invoice & Dunning agent: PDF tools + escalation ladder.

PDF generation runs locally (ReportLab); the escalation-ladder tests are pure
functions; the agent-registration test uses a Bedrock model-id *string*. None of
these need AWS. The live LLM-invokes-the-tool run still needs Bedrock access.
"""

from __future__ import annotations

import os

from pypdf import PdfReader

from agents import invoice_dunning
from agents.tools.guardrails_config import apply_tone_guardrail
from agents.tools.pdf_tool import generate_change_order_pdf, generate_invoice_pdf
from memory import schema

MODEL_ID = "anthropic.claude-3-5-sonnet-20241022-v2:0"


def _extract_text(path: str) -> str:
    reader = PdfReader(path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _client(payment_history, tone_log=None, **overrides):
    client = {
        "client_id": "client_001",
        "name": "Northwind Traders",
        "email": "accounts@northwind.example.com",
        "sow_terms": "{}",
        "billing_rate": 75.0,
        "payment_history": payment_history,
        "tone_log": tone_log or [],
    }
    client.update(overrides)
    return client


# --- Day 4: PDF tools -------------------------------------------------------


def test_generate_invoice_pdf_produces_pdf_with_expected_content(tmp_path, monkeypatch):
    monkeypatch.setenv("PDF_OUTPUT_DIR", str(tmp_path))

    path = generate_invoice_pdf(
        "client_001", 1200.0, "2026-09-06", client_name="Northwind Traders"
    )

    assert path.endswith(".pdf")
    assert os.path.isfile(path)

    text = _extract_text(path)
    assert "Northwind Traders" in text
    assert "client_001" in text
    assert "1,200.00" in text
    assert "2026-09-06" in text


def test_generate_change_order_pdf_produces_pdf(tmp_path, monkeypatch):
    monkeypatch.setenv("PDF_OUTPUT_DIR", str(tmp_path))

    path = generate_change_order_pdf("client_001", "Dark mode toggle", 3.0)

    assert path.endswith(".pdf")
    assert os.path.isfile(path)

    text = _extract_text(path)
    assert "Dark mode toggle" in text
    assert "3.0" in text


# --- Days 6-7: escalation ladder -------------------------------------------


def test_on_time_payer_produces_no_dunning_action():
    client = _client(
        [
            {
                "invoice_id": "inv_001",
                "amount": 1200.0,
                "due_date": "2026-08-01T00:00:00+00:00",
                "paid_date": "2026-08-02T00:00:00+00:00",
                "status": "paid",
            }
        ]
    )
    assert invoice_dunning.check_due_dates(client, "2026-08-20T00:00:00+00:00") == []


def test_late_payer_gets_day_7_notice_with_late_fee():
    client = _client(
        [
            {
                "invoice_id": "inv_002",
                "amount": 1200.0,
                "due_date": "2026-08-12T00:00:00+00:00",
                "status": "unpaid",
            }
        ]
    )
    actions = invoice_dunning.check_due_dates(client, "2026-08-20T00:00:00+00:00")

    assert len(actions) == 1
    action = actions[0]
    assert action["action_type"] == "dunning_email"
    assert action["escalation_tier"] == "day_7"
    assert action["requires_human_approval"] is True
    assert "Overdue invoice inv_002" in action["drafted_content"]
    assert "75.00" in action["drafted_content"]  # late fee = max(75, 1200*5%)


def test_never_payer_gets_day_14_work_pause_warning():
    client = _client(
        [
            {
                "invoice_id": "inv_003",
                "amount": 2400.0,
                "due_date": "2026-07-30T00:00:00+00:00",
                "status": "unpaid",
            }
        ],
        tone_log=[
            {"date": "2026-08-02", "escalation_tier": "day_3", "summary": "Reminder for inv_003."},
            {"date": "2026-08-06", "escalation_tier": "day_7", "summary": "Notice for inv_003."},
        ],
    )
    actions = invoice_dunning.check_due_dates(client, "2026-08-20T00:00:00+00:00")

    assert len(actions) == 1
    action = actions[0]
    assert action["escalation_tier"] == "day_14"
    assert action["requires_human_approval"] is True
    assert "pause" in action["drafted_content"].lower()


def test_same_tier_is_not_reset_for_same_invoice():
    client = _client(
        [
            {
                "invoice_id": "inv_004",
                "amount": 1000.0,
                "due_date": "2026-08-13T00:00:00+00:00",
                "status": "unpaid",
            }
        ],
        tone_log=[
            {"date": "2026-08-16", "escalation_tier": "day_7", "summary": "Notice for inv_004."},
        ],
    )
    # 7 days overdue, but day_7 already sent -> no new action (no downgrade).
    assert invoice_dunning.check_due_dates(client, "2026-08-20T00:00:00+00:00") == []


# --- milestone -> invoice proposals (Phase 3 dashboard trigger) -------------


def _milestone_client(**overrides):
    client = _client([])
    client[schema.MILESTONES] = [
        {
            "milestone_id": "landing_page",
            "name": "Landing page",
            "amount": 1200.0,
            "status": "complete",
            "completed_at": "2026-08-06T00:00:00+00:00",
        }
    ]
    client.update(overrides)
    return client


def test_check_milestones_proposes_invoice_for_completed_milestone(tmp_path, monkeypatch):
    monkeypatch.setenv("PDF_OUTPUT_DIR", str(tmp_path))
    client = _milestone_client()

    proposals = invoice_dunning.check_milestones(client)

    assert len(proposals) == 1
    action = proposals[0]
    assert action[schema.ACTION_TYPE] == "invoice"
    assert action[schema.DRAFTED_CONTENT].endswith(".pdf")
    assert os.path.isfile(action[schema.DRAFTED_CONTENT])
    assert "Landing page" in action[schema.AGENT_REASONING]
    assert "1,200.00" in action[schema.AGENT_REASONING]
    assert action[invoice_dunning.REQUIRES_HUMAN_APPROVAL] is True


def test_check_milestones_ignores_incomplete_and_already_invoiced(tmp_path, monkeypatch):
    monkeypatch.setenv("PDF_OUTPUT_DIR", str(tmp_path))
    client = _milestone_client(
        milestones=[
            {
                "milestone_id": "not_done",
                "name": "Not done",
                "amount": 500.0,
                "status": "in_progress",
                "completed_at": None,
            }
        ],
        payment_history=[
            {
                "invoice_id": "inv_done",
                "milestone_id": "landing_page",
                "amount": 1200.0,
                "status": "paid",
            }
        ],
    )
    # "landing_page" is in payment_history; "not_done" isn't complete -> nothing.
    assert invoice_dunning.check_milestones(client) == []


def test_propose_invoice_due_date_defaults_to_net_14():
    milestone = {
        "milestone_id": "m",
        "name": "Contact form",
        "amount": 800.0,
        "status": "complete",
        "completed_at": "2026-08-06T00:00:00+00:00",
    }
    assert invoice_dunning.default_due_date("2026-08-06T00:00:00+00:00") == "2026-08-20"


# --- tone guardrail ---------------------------------------------------------


def test_guardrail_rewrites_aggressive_tone():
    result = apply_tone_guardrail("PAY US NOW OR WE SUE YOU!!!", "day_7")
    assert result != "PAY US NOW OR WE SUE YOU!!!"
    assert "sue" not in result.lower()
    assert "polite" in result.lower()


def test_guardrail_passes_clean_draft_through():
    clean = "This is a polite reminder that your invoice is now past due."
    assert apply_tone_guardrail(clean, "day_7") == clean


# --- agent wiring -----------------------------------------------------------


def test_invoice_dunning_agent_registers_pdf_tools():
    agent = invoice_dunning.build_invoice_dunning_agent(MODEL_ID)
    assert "generate_invoice_pdf" in agent.tool_names
    assert "generate_change_order_pdf" in agent.tool_names
    assert "apply_tone_guardrail" in agent.tool_names
