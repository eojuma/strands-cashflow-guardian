"""Tests for the PDF output directory resolution.

Regression: in AWS Lambda the task root (``/var/task``) is read-only, so the
default relative ``generated/`` dir raised ``OSError: Read-only file system``.
"""

from __future__ import annotations

from pathlib import Path

from agents.tools import pdf_tool


def test_output_dir_defaults_to_tmp_in_lambda(monkeypatch):
    monkeypatch.delenv("PDF_OUTPUT_DIR", raising=False)
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "cashflow-guardian")
    assert pdf_tool._output_dir() == Path("/tmp/generated")


def test_output_dir_defaults_to_generated_locally(monkeypatch):
    monkeypatch.delenv("PDF_OUTPUT_DIR", raising=False)
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    assert pdf_tool._output_dir() == Path("generated").resolve()


def test_output_dir_honors_explicit_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("PDF_OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "cashflow-guardian")
    assert pdf_tool._output_dir() == (tmp_path / "out").resolve()
