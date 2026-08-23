"""Day 5 tests for the Gmail tools.

The Gmail service is mocked (no OAuth token, no network), so these verify the
read/send logic — message parsing and MIME construction — without credentials.
"""

from __future__ import annotations

import base64
from email import message_from_bytes

import pytest

from agents.tools import gmail_tool


class _Response:
    def __init__(self, data):
        self._data = data

    def execute(self):
        return self._data


class FakeGmailService:
    def __init__(self, list_result=None, get_map=None):
        self.list_result = list_result or {"messages": []}
        self.get_map = get_map or {}
        self.sent_bodies = []

    def users(self):
        return self

    def messages(self):
        return self

    def list(self, **kwargs):
        self._last_list_kwargs = kwargs
        return _Response(self.list_result)

    def get(self, **kwargs):
        return _Response(self.get_map[kwargs["id"]])

    def send(self, **kwargs):
        self.sent_bodies.append(kwargs["body"])
        return _Response({"id": "sent_1", "labelIds": ["SENT"]})


def _message(overrides=None):
    payload = {
        "headers": [
            {"name": "From", "value": "client@example.com"},
            {"name": "Subject", "value": "Quick tweak"},
            {"name": "Date", "value": "Mon, 17 Aug 2026 09:00:00 -0400"},
        ],
        "mimeType": "text/plain",
        "body": {"data": base64.urlsafe_b64encode(b"Add a dark mode toggle").decode()},
    }
    message = {"id": "abc123", "snippet": "Add a dark mode toggle", "payload": payload}
    message.update(overrides or {})
    return message


def test_read_recent_emails_parses_sender_subject_and_body(monkeypatch):
    fake = FakeGmailService(
        list_result={"messages": [{"id": "abc123"}]},
        get_map={"abc123": _message()},
    )
    monkeypatch.setattr(gmail_tool, "_build_service", lambda: fake)

    emails = gmail_tool.read_recent_emails("2026-08-16T00:00:00Z")

    assert len(emails) == 1
    assert emails[0]["sender"] == "client@example.com"
    assert emails[0]["subject"] == "Quick tweak"
    assert "dark mode toggle" in emails[0]["body"]
    assert emails[0]["received_at"].startswith("Mon, 17 Aug 2026")
    # The Gmail query must be date-scoped, not fetch the whole inbox.
    assert "after:2026/08/16" in fake._last_list_kwargs["q"]


def test_send_email_builds_mime_and_returns_true(monkeypatch):
    fake = FakeGmailService()
    monkeypatch.setattr(gmail_tool, "_build_service", lambda: fake)

    result = gmail_tool.send_email("client@example.com", "Invoice", "Please find attached.")

    assert result is True
    assert len(fake.sent_bodies) == 1

    decoded = base64.urlsafe_b64decode(fake.sent_bodies[0]["raw"])
    msg = message_from_bytes(decoded)
    assert msg["To"] == "client@example.com"
    assert msg["Subject"] == "Invoice"
    assert "Please find attached." in msg.get_payload()


def test_build_service_without_credentials_fails_loudly(monkeypatch, tmp_path):
    monkeypatch.setenv("GMAIL_TOKEN_FILE", str(tmp_path / "token.json"))
    monkeypatch.setenv("GMAIL_CLIENT_SECRET_FILE", str(tmp_path / "client_secret.json"))

    with pytest.raises(RuntimeError, match="Gmail OAuth is not configured"):
        gmail_tool._build_service()
