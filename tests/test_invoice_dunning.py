"""Day 4 smoke tests for the PDF tool and its registration on the agent.

The PDF generation tests run without AWS (ReportLab writes locally). The agent
registration test uses a Bedrock model-id *string* (no network). The live
LLM-invokes-the-tool run still needs real Bedrock access.
"""

from __future__ import annotations

import os

from pypdf import PdfReader

from agents import invoice_dunning
from agents.tools.pdf_tool import generate_change_order_pdf, generate_invoice_pdf

MODEL_ID = "anthropic.claude-3-5-sonnet-20241022-v2:0"


def _extract_text(path: str) -> str:
    reader = PdfReader(path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


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


def test_invoice_dunning_agent_registers_pdf_tools():
    agent = invoice_dunning.build_invoice_dunning_agent(MODEL_ID)
    assert "generate_invoice_pdf" in agent.tool_names
    assert "generate_change_order_pdf" in agent.tool_names
