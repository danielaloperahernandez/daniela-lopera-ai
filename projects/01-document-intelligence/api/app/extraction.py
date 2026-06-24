"""PDF text extraction + LLM structured parsing.

This is the "complex logic" that justifies a Python service instead of doing it in n8n:
robust PDF parsing plus a schema-constrained LLM call with retries.
"""

from __future__ import annotations

import io

from pypdf import PdfReader

from ai_core import load_prompt, structured_chat

from .schemas import InvoiceData


def extract_pdf_text(content: bytes) -> tuple[str, int]:
    """Return ``(text, page_count)`` from raw PDF bytes."""
    reader = PdfReader(io.BytesIO(content))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages).strip(), len(reader.pages)


def parse_invoice(document_text: str, *, doc_type: str = "invoice") -> InvoiceData:
    """Use the LLM to extract structured invoice fields from raw text."""
    prompt = load_prompt("document_extraction")
    system, user = prompt.render(doc_type=doc_type, document_text=document_text)
    return structured_chat(InvoiceData, system, user, temperature=0.0)
