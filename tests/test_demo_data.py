from datetime import date

from agents import invoice_dunning, scope_sentinel
from memory import schema
from scripts.seed_demo_data import demo_clients, demo_scope_email


TODAY = date(2026, 8, 25)


def test_demo_personas_produce_expected_agent_judgments(monkeypatch, tmp_path):
    monkeypatch.setenv("PDF_OUTPUT_DIR", str(tmp_path))
    clients = {c[schema.CLIENT_ID]: c for c in demo_clients(TODAY)}
    today = TODAY.isoformat()
    assert invoice_dunning.check_due_dates(clients["demo_on_time"], today) == []
    overdue = invoice_dunning.check_due_dates(clients["demo_late"], today)
    assert len(overdue) == 1
    assert overdue[0][schema.ESCALATION_TIER] == "day_7"
    scope = scope_sentinel.check_inbox([demo_scope_email(TODAY)], clients["demo_scope"])
    assert len(scope) == 1
    assert scope[0][schema.ACTION_TYPE] == "change_order"
    assert "dark mode" in scope[0][schema.AGENT_REASONING].lower()
