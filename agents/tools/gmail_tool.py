"""Gmail API tools — read + send email.

Both functions are registered as Strands ``@tool``s. ``read_recent_emails`` feeds
the Scope Creep Sentinel (a later day); ``send_email`` is the low-level primitive
the Orchestrator's deterministic execution path calls *after* a human approves an
action.

Auth (OAuth, Desktop-app flow):

- ``GMAIL_CLIENT_SECRET_FILE`` — path to the downloaded ``client_secret.json``.
- ``GMAIL_TOKEN_FILE`` — path to the token produced by the one-time consent flow
  (defaults to ``credentials/token.json``). If the token is absent but the client
  secret exists, the first call runs the local browser consent flow once and
  writes the token. Both files are gitignored.

Until those files exist, the tools fail loudly with a clear message rather than
silently no-oping.
"""

from __future__ import annotations

import base64
import os
from email.mime.text import MIMEText
from pathlib import Path

from strands import tool

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]

_CREDENTIALS_DIR = Path(__file__).resolve().parents[2] / "credentials"


def _token_path() -> Path:
    return Path(os.getenv("GMAIL_TOKEN_FILE", str(_CREDENTIALS_DIR / "token.json")))


def _client_secret_path() -> Path:
    return Path(
        os.getenv("GMAIL_CLIENT_SECRET_FILE", str(_CREDENTIALS_DIR / "client_secret.json"))
    )


def _load_credentials():
    """Return Google OAuth credentials, running the consent flow on first use."""
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    token_path = _token_path()
    if token_path.exists():
        return Credentials.from_authorized_user_file(str(token_path), SCOPES)

    secret_path = _client_secret_path()
    if not secret_path.exists():
        raise RuntimeError(
            "Gmail OAuth is not configured. Set GMAIL_CLIENT_SECRET_FILE to the "
            "downloaded client_secret.json and run once to authorize, or set "
            "GMAIL_TOKEN_FILE to an existing token. Until then read/send cannot run."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(secret_path), SCOPES)
    credentials = flow.run_local_server(port=0)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(credentials.to_json())
    return credentials


def _build_service():
    """Build an authorized Gmail API service (imports are local to keep the
    module importable without the Google client installed)."""
    from googleapiclient.discovery import build

    return build("gmail", "v1", credentials=_load_credentials())


def _to_gmail_date(since: str) -> str:
    """Convert an ISO 8601 datetime to Gmail's ``after:`` query format."""
    from datetime import datetime

    dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
    return dt.strftime("%Y/%m/%d")


def _extract_body(payload: dict) -> str:
    """Recursively pull the first text/plain body out of a message payload."""
    if not payload:
        return ""
    if payload.get("mimeType") == "text/plain":
        data = (payload.get("body") or {}).get("data")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        return ""
    for part in payload.get("parts", []):
        text = _extract_body(part)
        if text:
            return text
    return ""


def _parse_message(message: dict) -> dict:
    payload = message.get("payload", {})
    headers = {h["name"]: h["value"] for h in payload.get("headers", [])}
    return {
        "sender": headers.get("From", ""),
        "subject": headers.get("Subject", ""),
        "received_at": headers.get("Date", ""),
        "body": _extract_body(payload) or message.get("snippet", ""),
    }


@tool
def read_recent_emails(since: str) -> list[dict]:
    """Fetch recent emails received since a given datetime.

    Args:
        since: ISO 8601 datetime string (e.g. 2026-08-16T00:00:00Z). Emails
            received after this point are returned.

    Returns:
        A list of dicts, each with keys: sender, subject, body, received_at.
    """
    service = _build_service()
    date_query = _to_gmail_date(since)

    results = (
        service.users()
        .messages()
        .list(userId="me", q=f"after:{date_query}", maxResults=10)
        .execute()
    )

    emails = []
    for item in results.get("messages", []):
        full = (
            service.users()
            .messages()
            .get(userId="me", id=item["id"], format="full")
            .execute()
        )
        emails.append(_parse_message(full))
    return emails


@tool
def send_email(to: str, subject: str, body: str) -> bool:
    """Send a plain-text email.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        body: Plain-text email body.

    Returns:
        True when the send succeeds.
    """
    service = _build_service()
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return True
