"""Structural tests for Day 3 orchestration wiring.

These run without any AWS call: ``build_orchestrator`` is given a Bedrock
model-id *string*, which Strands accepts without touching the network. They pin
the one thing that matters most for Day 3 — that delegation goes through the
native agents-as-tools pattern, not ``if/else`` routing.

The live end-to-end run (an actual LLM routing a milestone event to the
specialist) still needs real Bedrock access; see ``agents/orchestrator.py``.
"""

from __future__ import annotations

from strands import Agent

from agents import invoice_dunning
from agents.orchestrator import (
    FAKE_TRIGGER,
    ORCHESTRATOR_SYSTEM_PROMPT,
    build_orchestrator,
)
from agents.tools import build_sub_agent_tools

MODEL_ID = "anthropic.claude-3-5-sonnet-20241022-v2:0"


def test_orchestrator_registers_invoice_dunning_as_tool():
    orchestrator = build_orchestrator(model=MODEL_ID)
    assert isinstance(orchestrator, Agent)
    assert "invoice_dunning" in orchestrator.tool_names


def test_sub_agent_is_exposed_as_agent_tool_not_function():
    tools = build_sub_agent_tools(MODEL_ID)
    assert len(tools) == 1
    tool = tools[0]
    # "agent" tool_type == agents-as-tools (Agent.as_tool()), not a plain @tool.
    assert tool.tool_type == "agent"
    assert tool.tool_name == "invoice_dunning"


def test_orchestrator_system_prompt_instructs_routing():
    assert "invoice_dunning" in ORCHESTRATOR_SYSTEM_PROMPT
    orchestrator = build_orchestrator(model=MODEL_ID)
    assert "invoice_dunning" in orchestrator.system_prompt


def test_invoice_dunning_prompt_instructs_pdf_generation():
    agent = invoice_dunning.build_invoice_dunning_agent(MODEL_ID)
    assert "milestone" in agent.system_prompt
    assert "generate_invoice_pdf" in agent.system_prompt


def test_fake_trigger_describes_a_milestone_complete_event():
    assert "milestone complete" in FAKE_TRIGGER
    assert "client_001" in FAKE_TRIGGER
