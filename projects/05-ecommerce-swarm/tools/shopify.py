"""Tools de Shopify Admin API REST con requests y ShopifyClient reutilizable."""

import re
from html import unescape
from typing import Any, Optional

import requests
from langchain_core.tools import tool
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import get_settings

# Cliente singleton por proceso
_client: Optional["ShopifyClient"] = None


class ShopifyAPIError(Exception):
    """Error de la API de Shopify con mensaje amigable para el usuario."""

    def __init__(self, user_message: str):
        self.user_message = user_message
        super().__init__(user_message)


class ShopifyClient:
    """Cliente HTTP reutilizable para Shopify Admin API REST."""

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.shopify_base_url
        self.session = requests.Session()
        self.session.headers.update(
            {
                "X-Shopify-Access-Token": settings.shopify_access_token,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )
        retries = Retry(
            total=2,
            backoff_factor=1,
            status_forcelist=[502, 503, 504],
            allowed_methods=["GET", "POST"],
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retries))

    def _handle_response(self, resp: requests.Response) -> dict[str, Any]:
        if resp.status_code == 401:
            raise ShopifyAPIError(
                "No pude conectar con la tienda (error de autenticación). "
                "Por favor intenta más tarde o escribe *hablar con un asesor*."
            )
        if resp.status_code == 404:
            raise ShopifyAPIError(
                "No encontré ese registro en la tienda. "
                "Verifica el dato e intenta de nuevo."
            )
        if resp.status_code == 429:
            raise ShopifyAPIError(
                "La tienda está recibiendo muchas consultas en este momento. "
                "Espera unos segundos e intenta de nuevo, por favor."
            )
        if resp.status_code >= 400:
            raise ShopifyAPIError(
                f"Hubo un problema al consultar la tienda (código {resp.status_code}). "
                "Intenta de nuevo en un momento."
            )
        return resp.json()

    def get(self, path: str, params: dict | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        resp = self.session.get(url, params=params or {}, timeout=30)
        return self._handle_response(resp)

    def post(self, path: str, body: dict) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        resp = self.session.post(url, json=body, timeout=30)
        return self._handle_response(resp)


def get_client() -> ShopifyClient:
    global _client
    if _client is None:
        _client = ShopifyClient()
    return _client


def _normalize_phone(phone: str) -> str:
    return "".join(c for c in phone if c.isdigit())


def _phones_match(phone_a: str, phone_b: str) -> bool:
    a, b = _normalize_phone(phone_a), _normalize_phone(phone_b)
    if not a or not b:
        return False
    if len(a) >= 10 and len(b) >= 10:
        return a[-10:] == b[-10:]
    return a == b


def _phone_search_variants(phone: str) -> list[str]:
    """
    Genera variantes de búsqueda para Colombia:
    +57XXXXXXXXXX, sin prefijo, solo dígitos con +57.
    """
    digits = _normalize_phone(phone)
    variants: list[str] = []

    if digits.startswith("57") and len(digits) > 10:
        local = digits[2:]
        variants.extend([f"+{digits}", f"+57{local}", local, digits])
    else:
        variants.extend([f"+57{digits}", digits, f"+{digits}"])

    seen: set[str] = set()
    unique: list[str] = []
    for v in variants:
        if v and v not in seen:
            seen.add(v)
            unique.append(v)
    return unique


def _search_customer_by_phone(phone: str) -> dict | None:
    client = get_client()
    for variant in _phone_search_variants(phone):
        data = client.get("/customers/search.json", {"query": f"phone:{variant}"})
        customers = data.get("customers", [])
        if customers:
            return customers[0]
    return None


def _strip_html(text: str) -> str:
    clean = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", clean)).strip()


def _format_money(amount: str | float, currency: str = "COP") -> str:
    try:
        value = float(amount)
        if currency == "COP":
            return f"${value:,.0f} {currency}".replace(",", ".")
        return f"${value:,.2f} {currency}"
    except (TypeError, ValueError):
        return str(amount)


def _format_status(status: str | None) -> str:
    labels = {
        "fulfilled": "Despachado",
        "partial": "Despacho parcial",
        "unfulfilled": "En preparación",
        "paid": "Pagado",
        "pending": "Pago pendiente",
        "refunded": "Reembolsado",
        "voided": "Anulado",
    }
    return labels.get(status or "", status or "Sin estado")


@tool
def search_products(
    query: str,
    max_price: Optional[float] = None,
    category: Optional[str] = None,
) -> str:
    """Busca productos en Shopify por nombre, categoría o precio máximo."""
    try:
        client = get_client()
        params: dict = {"limit": 5, "status": "active"}
        if query:
            params["title"] = query

        data = client.get("/products.json", params)
        products = data.get("products", [])

        if category:
            cat_lower = category.lower()
            products = [
                p
                for p in products
                if cat_lower in (p.get("product_type") or "").lower()
                or any(cat_lower in tag.strip().lower() for tag in (p.get("tags") or "").split(","))
            ]

        lines = [f"*Resultados para \"{query}\"*\n"]
        count = 0
        for p in products:
            variants = p.get("variants", [])
            price = float(variants[0]["price"]) if variants else 0.0
            if max_price is not None and price > max_price:
                continue
            stock = sum(v.get("inventory_quantity", 0) or 0 for v in variants)
            count += 1
            avail = "Disponible" if stock > 0 else "Agotado"
            lines.append(
                f"- *{p['title']}*\n"
                f"  Precio: {_format_money(price)}\n"
                f"  Estado: {avail} | ID: {p['id']}"
            )

        if count == 0:
            return "No encontré productos con esos criterios. ¿Quieres probar con otro nombre o categoría?"
        lines.append(f"\n_Mostré {count} producto(s). Pide el ID para ver más detalles._")
        return "\n".join(lines)

    except ShopifyAPIError as e:
        return e.user_message


@tool
def get_product_detail(product_id: str) -> str:
    """Retorna detalle completo de un producto: precio, stock, variantes, descripción."""
    try:
        client = get_client()
        data = client.get(f"/products/{product_id}.json")
        p = data.get("product", {})

        lines = [
            f"*{p.get('title', 'Producto')}*",
            f"Categoría: {p.get('product_type') or 'General'}",
            "",
        ]

        desc = _strip_html(p.get("body_html") or "")
        if desc:
            lines.append(f"{desc[:400]}{'...' if len(desc) > 400 else ''}\n")

        lines.append("*Variantes:*")
        for v in p.get("variants", []):
            stock = v.get("inventory_quantity", 0) or 0
            lines.append(
                f"- {v.get('title')}: {_format_money(v.get('price', 0))} "
                f"({'En stock' if stock > 0 else 'Agotado'})"
            )

        return "\n".join(lines)

    except ShopifyAPIError as e:
        return e.user_message


@tool
def get_order_by_number(order_number: str, customer_phone: str) -> str:
    """Busca un pedido por número. Valida que el teléfono coincida con el cliente."""
    try:
        client = get_client()
        name = order_number if order_number.startswith("#") else f"#{order_number}"
        data = client.get("/orders.json", {"name": name, "status": "any", "limit": 1})
        orders = data.get("orders", [])

        if not orders:
            return f"No encontré el pedido *{name}*. Revisa el número en tu confirmación de compra."

        order = orders[0]
        order_phone = order.get("phone") or (order.get("billing_address") or {}).get("phone", "")
        customer = order.get("customer") or {}
        cust_phone = customer.get("phone") or order_phone

        if not _phones_match(customer_phone, cust_phone):
            return (
                "Por tu seguridad, el teléfono de este chat no coincide con el registrado en el pedido.\n"
                "Verifica el número de pedido o escribe *hablar con un asesor* para ayudarte."
            )

        lines = [
            f"*Pedido {order['name']}*",
            f"Estado de pago: {_format_status(order.get('financial_status'))}",
            f"Estado de envío: {_format_status(order.get('fulfillment_status'))}",
            f"Total: {_format_money(order.get('total_price', 0), order.get('currency', 'COP'))}",
            f"Fecha: {(order.get('created_at') or '')[:10]}",
            "",
            "*Productos:*",
        ]
        for li in order.get("line_items", []):
            lines.append(f"- {li['title']} x{li['quantity']}")

        fulfillments = order.get("fulfillments", [])
        tracking = [
            f"{f.get('tracking_company')}: {f.get('tracking_number')}"
            for f in fulfillments
            if f.get("tracking_number")
        ]
        if tracking:
            lines.extend(["", "*Rastreo:*", *[f"- {t}" for t in tracking]])

        lines.append(f"\n_ID interno del pedido: {order['id']}_")
        return "\n".join(lines)

    except ShopifyAPIError as e:
        return e.user_message


@tool
def get_customer_orders(phone: str) -> str:
    """Retorna los últimos 5 pedidos de un cliente buscado por teléfono."""
    try:
        customer = _search_customer_by_phone(phone)
        if not customer:
            return (
                f"No encontré una cuenta asociada al teléfono *{phone}*.\n"
                "¿Usaste otro número al comprar?"
            )

        client = get_client()
        orders_data = client.get(
            "/orders.json",
            {"customer_id": customer["id"], "status": "any", "limit": 5},
        )
        orders = orders_data.get("orders", [])
        name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()

        if not orders:
            return f"Hola {name or 'cliente'}, no tienes pedidos registrados aún."

        lines = [f"*Últimos pedidos de {name or 'tu cuenta'}*\n"]
        for o in orders:
            status = _format_status(o.get("fulfillment_status") or o.get("financial_status"))
            lines.append(
                f"- *{o['name']}* — {status}\n"
                f"  {_format_money(o.get('total_price', 0), o.get('currency', 'COP'))} "
                f"| {(o.get('created_at') or '')[:10]}"
            )
        lines.append(f"\n_ID de cliente: {customer['id']}_")
        return "\n".join(lines)

    except ShopifyAPIError as e:
        return e.user_message


@tool
def get_customer_by_phone(phone: str) -> str:
    """Busca un cliente en Shopify por número de teléfono."""
    try:
        customer = _search_customer_by_phone(phone)
        if not customer:
            return (
                f"No encontré una cuenta con el teléfono *{phone}*.\n"
                "Si compraste con otro número, indícamelo por favor."
            )

        name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
        return (
            f"*Cliente encontrado*\n"
            f"- Nombre: {name or 'No registrado'}\n"
            f"- Email: {customer.get('email') or 'No registrado'}\n"
            f"- Teléfono: {customer.get('phone') or phone}\n"
            f"- Pedidos realizados: {customer.get('orders_count', 0)}\n"
            f"- Total comprado: {_format_money(customer.get('total_spent', 0))}\n"
            f"- ID de cliente: {customer['id']}"
        )

    except ShopifyAPIError as e:
        return e.user_message


@tool
def create_refund(
    order_id: str,
    reason: str,
    line_item_ids: Optional[list] = None,
) -> str:
    """Crea una solicitud de reembolso en Shopify."""
    try:
        client = get_client()
        order_data = client.get(f"/orders/{order_id}.json")
        order = order_data.get("order", {})

        if order.get("financial_status") == "refunded":
            return "Este pedido ya fue reembolsado por completo."

        refund_line_items = []
        for li in order.get("line_items", []):
            if line_item_ids and li["id"] not in line_item_ids:
                continue
            refund_line_items.append(
                {
                    "line_item_id": li["id"],
                    "quantity": li["quantity"],
                    "restock_type": "return",
                }
            )

        if not refund_line_items:
            return "No hay productos elegibles para reembolso en este pedido."

        transactions = []
        for t in order.get("transactions", []):
            if t.get("kind") == "sale" and t.get("status") == "success":
                transactions.append(
                    {
                        "parent_id": t["id"],
                        "amount": t["amount"],
                        "kind": "refund",
                        "gateway": t.get("gateway"),
                    }
                )
                break

        body = {
            "refund": {
                "note": reason,
                "notify": True,
                "shipping": {"full_refund": True},
                "refund_line_items": refund_line_items,
                "transactions": transactions,
            }
        }

        result = client.post(f"/orders/{order_id}/refunds.json", body)
        refund = result.get("refund", {})
        return (
            f"*Reembolso iniciado*\n"
            f"- Pedido ID: {order_id}\n"
            f"- Motivo: {reason}\n"
            f"- Referencia: {refund.get('id', 'pendiente')}\n\n"
            "Recibirás confirmación por email. El reembolso puede tardar 5-10 días hábiles "
            "según tu banco o medio de pago."
        )

    except ShopifyAPIError as e:
        return e.user_message
