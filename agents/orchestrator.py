"""Orchestrator agent — Day 1 skeleton.

Proves the foundation works end to end: one Bedrock call through the Strands
Agents SDK, before any real agent logic is added. Later days turn this file
into the entry point that owns the human-in-the-loop state machine and
delegates to the Scope Creep Sentinel and Invoice & Dunning specialist agents.

Run locally with:

    python agents/orchestrator.py
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from strands import Agent
from strands.models import BedrockModel

DEFAULT_MODEL_ID = "anthropic.claude-3-5-sonnet-20241022-v2:0"


def _load_env() -> None:
    """Load `.env` from the repo root if present (the file is never committed)."""
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        load_dotenv(env_path)


def main() -> None:
    _load_env()

    model_id = os.getenv("BEDROCK_MODEL_ID", DEFAULT_MODEL_ID)
    if not model_id:
        raise SystemExit(
            "BEDROCK_MODEL_ID is not set. Copy .env.example to .env and fill it in."
        )

    model = BedrockModel(model_id=model_id, temperature=0.3, streaming=False)
    agent = Agent(model=model)

    # Deterministic, hardcoded prompt so the Day 1 acceptance check is clear:
    # the run must return a real Bedrock-generated response.
    prompt = (
        "Reply with exactly this sentence and nothing else: "
        "'CashflowGuardian foundation is live.'"
    )
    print(agent(prompt))


if __name__ == "__main__":
    main()
