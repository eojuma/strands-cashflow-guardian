from datetime import date

from agents import invoice_dunning, scope_sentinel
from memory import schema
from scripts.seed_demo_data import demo_clients, demo_scope_email


TODAY = date(2026, 8, 25)


def _clients():
    return {c[schema.CLIENT_ID]: c for c in demo_clients(TODAY)}


def test_demo_personas_produce_expected_agent_judgments(monkeypatch, tmp_path):
    monkeypatch.setenv("PDF_OUTPUT_DIR", str(tmp_path))
    clients = _clients()
    today = TODAY.isoformat()

    assert len(clients) == 5
    assert invoice_dunning.check_due_dates(clients["client_on_time"], today) == []
    assert invoice_dunning.check_due_dates(clients["client_clean"], today) == []

    # 6 days past due -> first threshold (day_3 friendly check-in).
    late = invoice_dunning.check_due_dates(clients["client_late"], today)
    assert len(late) == 1
    assert late[0][schema.ESCALATION_TIER] == "day_3"

    # 20 days past due with day_3/day_7 already logged -> day_14 final notice.
    late14 = invoice_dunning.check_due_dates(clients["client_late14"], today)
    assert len(late14) == 1
    assert late14[0][schema.ESCALATION_TIER] == "day_14"

    # Completed milestone -> one invoice proposal, never auto-generated before.
    invoiced = invoice_dunning.check_milestones(clients["client_scope"])
    assert len(invoiced) == 1
    assert invoiced[0][schema.ACTION_TYPE] == "invoice"
    assert invoiced[0]["amount"] == 2400.0

    # Inbound out-of-scope email -> change-order proposal.
    scope = scope_sentinel.check_inbox(
        [demo_scope_email(TODAY)], clients["client_scope"]
    )
    assert len(scope) == 1
    assert scope[0][schema.ACTION_TYPE] == "change_order"
    assert "dark mode" in scope[0][schema.AGENT_REASONING].lower()
