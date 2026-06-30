"""Esquemas Pydantic para webhooks y modelos de dominio."""

from typing import Any, List, Optional

from pydantic import BaseModel, Field


# --- WhatsApp Webhook ---


class WhatsAppText(BaseModel):
    body: str


class WhatsAppMessage(BaseModel):
    from_: str = Field(alias="from")
    id: str
    timestamp: str
    type: str
    text: Optional[WhatsAppText] = None

    model_config = {"populate_by_name": True}


class WhatsAppValue(BaseModel):
    messaging_product: str
    metadata: dict
    contacts: Optional[List[dict]] = None
    messages: Optional[List[WhatsAppMessage]] = None


class WhatsAppChange(BaseModel):
    value: WhatsAppValue
    field: str


class WhatsAppEntry(BaseModel):
    id: str
    changes: List[WhatsAppChange]


class WebhookPayload(BaseModel):
    object: str
    entry: List[WhatsAppEntry]


# --- Shopify (modelos de referencia) ---


class ShopifyVariant(BaseModel):
    id: int
    title: str
    price: str
    sku: Optional[str] = None
    inventory_quantity: Optional[int] = 0


class ShopifyProduct(BaseModel):
    id: int
    title: str
    body_html: Optional[str] = None
    vendor: Optional[str] = None
    product_type: Optional[str] = None
    tags: Optional[str] = None
    variants: List[ShopifyVariant] = []


class ShopifyLineItem(BaseModel):
    id: int
    title: str
    quantity: int
    price: str


class ShopifyOrder(BaseModel):
    id: int
    name: str
    financial_status: Optional[str] = None
    fulfillment_status: Optional[str] = None
    total_price: Optional[str] = None
    currency: Optional[str] = None
    phone: Optional[str] = None
    line_items: List[ShopifyLineItem] = []
    customer: Optional[dict[str, Any]] = None
