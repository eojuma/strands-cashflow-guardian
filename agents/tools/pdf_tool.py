"""PDF generation tools — the Invoice & Dunning agent's document layer.

Both functions are registered as Strands ``@tool``s so the LLM invokes them as
part of its reasoning loop (agents-as-tools / tool-calling), rather than
application code calling them directly. Each returns the absolute path to the
generated file; a later day can return an S3 key instead without changing the
caller.

Output directory: ``PDF_OUTPUT_DIR`` env var, defaulting to ``generated/`` under
the current working directory (gitignored).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from strands import tool

DEFAULT_OUTPUT_DIR = "generated"


def _output_dir() -> Path:
    return Path(os.getenv("PDF_OUTPUT_DIR", DEFAULT_OUTPUT_DIR)).resolve()


def _slug(value: str) -> str:
    """Make a value safe for use in a filename."""
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", value).strip("_") or "item"


def _currency(amount: float) -> str:
    return f"${amount:,.2f}"


def _draw_header(c: canvas.Canvas, title: str) -> None:
    width, height = LETTER
    c.setFont("Helvetica-Bold", 18)
    c.drawString(72, height - 72, "CashflowGuardian")
    c.setFont("Helvetica", 14)
    c.drawString(72, height - 96, title)
    c.line(72, height - 108, width - 72, height - 108)


def _draw_field(c: canvas.Canvas, y: float, label: str, value: str) -> None:
    c.setFont("Helvetica-Bold", 11)
    c.drawString(72, y, f"{label}:")
    c.setFont("Helvetica", 11)
    c.drawString(162, y, value)


@tool
def generate_invoice_pdf(
    client_id: str, amount: float, due_date: str, client_name: str = ""
) -> str:
    """Generate an invoice PDF for a completed milestone.

    Args:
        client_id: Unique client identifier (e.g. client_001).
        amount: Invoice amount in USD.
        due_date: Invoice due date as an ISO 8601 date string (e.g. 2026-09-06).
        client_name: Optional display name; falls back to client_id when empty.

    Returns:
        The absolute path to the generated PDF file.
    """
    output_dir = _output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"invoice_{_slug(client_id)}_{_slug(due_date)}.pdf"

    display_name = client_name or client_id
    c = canvas.Canvas(str(path), pagesize=LETTER)
    _draw_header(c, "Invoice")

    y = LETTER[1] - 140
    _draw_field(c, y, "Client", display_name)
    y -= 20
    _draw_field(c, y, "Client ID", client_id)
    y -= 20
    _draw_field(c, y, "Amount", _currency(amount))
    y -= 20
    _draw_field(c, y, "Due date", due_date)
    y -= 20

    c.setFont("Helvetica-Oblique", 10)
    c.drawString(72, y - 20, "Proposed by the Invoice & Dunning agent — pending human approval.")
    c.showPage()
    c.save()
    return str(path)


@tool
def generate_change_order_pdf(
    client_id: str, description: str, extra_hours: float, client_name: str = ""
) -> str:
    """Generate a change-order PDF for out-of-scope work.

    Args:
        client_id: Unique client identifier (e.g. client_001).
        description: What the out-of-scope work is.
        extra_hours: Estimated extra hours of work.
        client_name: Optional display name; falls back to client_id when empty.

    Returns:
        The absolute path to the generated PDF file.
    """
    output_dir = _output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"change_order_{_slug(client_id)}_{_slug(description)}.pdf"

    display_name = client_name or client_id
    c = canvas.Canvas(str(path), pagesize=LETTER)
    _draw_header(c, "Change Order")

    y = LETTER[1] - 140
    _draw_field(c, y, "Client", display_name)
    y -= 20
    _draw_field(c, y, "Client ID", client_id)
    y -= 20
    _draw_field(c, y, "Description", description)
    y -= 20
    _draw_field(c, y, "Extra hours", f"{extra_hours:.1f}")
    c.showPage()
    c.save()
    return str(path)
