"""Local dev API server for the Command Center dashboard.

Runs the same ``lambda_handlers.api_handler`` REST surface as plain HTTP on your
machine so you can run the full product locally without AWS. Standard-library
only — no Flask/FastAPI needed.

Usage:

    python scripts/serve_api.py            # http://localhost:8000
    python scripts/serve_api.py --port 9000

Then start the dashboard in another terminal:

    cd frontend && npm run dev             # proxies /api -> localhost:8000

Point both at real (or DynamoDB Local) storage via boto3's usual credential
chain or ``DYNAMODB_ENDPOINT_URL``.
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lambda_handlers import api_handler


class Handler(BaseHTTPRequestHandler):
    def _respond(self, response: dict) -> None:
        body = response["body"].encode("utf-8")
        self.send_response(response["statusCode"])
        for key, value in response["headers"].items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = {}
        self._respond(api_handler.route(self.command, self.path.split("?")[0], body))

    do_GET = _handle
    do_POST = _handle
    do_OPTIONS = _handle

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), fmt % args))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    server = HTTPServer((args.host, args.port), Handler)
    print(f"CashflowGuardian local API on http://{args.host}:{args.port}")
    print("Routes: GET /clients, GET /actions/pending, GET /activity-log,")
    print("POST /run-scheduled-check, POST /clients/{id}/milestone-complete, POST /actions/{id}/resolve")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
