"""API tests that run offline by faking the LLM extraction call."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.main as main_mod  # noqa: E402
from app.schemas import InvoiceData  # noqa: E402


@pytest.fixture
def client(monkeypatch) -> TestClient:
    monkeypatch.delenv("DOC_API_KEY", raising=False)
    return TestClient(main_mod.app)


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_extract_rejects_non_pdf(client: TestClient) -> None:
    resp = client.post(
        "/extract",
        files={"file": ("note.csv", b"a,b,c", "text/csv")},
    )
    assert resp.status_code == 415
    assert resp.json()["success"] is False


def test_extract_happy_path(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(main_mod, "extract_pdf_text", lambda content: ("INVOICE #42", 1))
    monkeypatch.setattr(
        main_mod,
        "parse_invoice",
        lambda text, **kw: InvoiceData(invoice_number="42", total=100.0, currency="USD"),
    )

    resp = client.post(
        "/extract",
        files={"file": ("invoice.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["invoice_number"] == "42"
    assert body["data"]["total"] == 100.0
