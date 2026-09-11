"""One-time Gmail OAuth consent flow -> ``credentials/token.json``.

Run this once, locally, after saving your OAuth *client* secret:

    python scripts/gmail_authorize.py

It opens a browser and asks you to grant Gmail access, then writes the token.
The Gmail API needs this token (a refresh token) in addition to
``client_secret.json``; the client secret alone cannot send mail.

After the token exists, redeploy so the Lambda bundles ``credentials/`` and
``CASHFLOW_SEND_MODE=live`` can send real email:

    SEND_MODE=live ./infra/deploy.sh
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

from agents.tools.gmail_tool import _client_secret_path, authorize_gmail


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    load_dotenv(repo / ".env")

    secret = _client_secret_path()
    if not secret.exists():
        raise SystemExit(
            f"Missing client secret at {secret}.\n"
            "Create an OAuth client (Desktop app) in Google Cloud Console, "
            "download the JSON, and save it there."
        )

    print(f"Using client secret: {secret}")
    token = authorize_gmail()
    print(f"\nGmail authorized. Token written to: {token}")
    print("Next: redeploy with SEND_MODE=live so the Lambda bundles credentials/.")


if __name__ == "__main__":
    main()
