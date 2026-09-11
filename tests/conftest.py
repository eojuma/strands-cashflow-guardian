"""Shared test configuration.

Keeps the developer's real environment out of the test run: a local
``credentials/token.json`` or a ``CASHFLOW_SEND_MODE`` set in the shell must not
change test outcomes. Tests that need Gmail/token behavior override these
explicitly via their own ``monkeypatch``.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_gmail_env(monkeypatch, tmp_path):
    # Point Gmail at a non-existent token and default to log mode. Individual
    # tests override as needed (e.g. to exercise the live/token paths).
    monkeypatch.setenv("GMAIL_TOKEN_FILE", str(tmp_path / "no-token.json"))
    monkeypatch.setenv("CASHFLOW_SEND_MODE", "log")
