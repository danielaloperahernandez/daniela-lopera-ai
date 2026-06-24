"""Request/response schemas for the extraction API.

The target schema models an invoice, a common real-world document. The LLM is asked to fill
exactly this structure; missing fields come back as ``null`` rather than being invented.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LineItem(BaseModel):
    description: str | None = Field(default=None, description="Line item description.")
    quantity: float | None = Field(default=None, description="Units billed.")
    unit_price: float | None = Field(default=None, description="Price per unit.")
    amount: float | None = Field(default=None, description="Line total.")


class InvoiceData(BaseModel):
    """The structured fields we extract from an invoice PDF."""

    invoice_number: str | None = Field(default=None)
    issue_date: str | None = Field(default=None, description="ISO date YYYY-MM-DD.")
    due_date: str | None = Field(default=None, description="ISO date YYYY-MM-DD.")
    vendor_name: str | None = Field(default=None)
    customer_name: str | None = Field(default=None)
    currency: str | None = Field(default=None, description="3-letter currency code.")
    subtotal: float | None = Field(default=None)
    tax: float | None = Field(default=None)
    total: float | None = Field(default=None)
    line_items: list[LineItem] = Field(default_factory=list)


class ExtractionResponse(BaseModel):
    """Envelope returned to the caller (e.g. n8n)."""

    success: bool
    filename: str
    pages: int
    characters: int
    data: InvoiceData


class HealthResponse(BaseModel):
    status: str = "ok"
    provider: str
    model: str
