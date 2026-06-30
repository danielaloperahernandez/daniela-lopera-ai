#!/usr/bin/env python
"""
Prueba local del grafo LangGraph sin WhatsApp, webhook ni APIs externas.

Uso (desde projects/05-ecommerce-swarm/):
    python test_graph.py

Opcional: si GEMINI_API_KEY está configurada, usa Gemini real para LLM
y solo mockea Redis, Shopify y ChromaDB.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable

# Variables mínimas antes de importar módulos del proyecto
os.environ.setdefault("GEMINI_API_KEY", "test-local-key")
os.environ.setdefault("SHOPIFY_STORE_URL", "tienda-demo.myshopify.com")
os.environ.setdefault("SHOPIFY_ACCESS_TOKEN", "shpat_test_token")
os.environ.setdefault("WHATSAPP_TOKEN", "test_whatsapp_token")
os.environ.setdefault("WHATSAPP_PHONE_ID", "100000000000000")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test_verify")
os.environ.setdefault("WHATSAPP_APP_SECRET", "test_secret")
os.environ.setdefault("REDIS_URL", "redis://fake:6379/0")

# ---------------------------------------------------------------------------
# FakeRedis — dict en memoria compatible con memory/session.py
# ---------------------------------------------------------------------------


class FakePipeline:
    def __init__(self, redis: "FakeRedis") -> None:
        self._redis = redis
        self._ops: list[tuple] = []

    def zremrangebyscore(self, key: str, min_score: float, max_score: float) -> None:
        self._ops.append(("zremrangebyscore", key, min_score, max_score))

    def zadd(self, key: str, mapping: dict[str, float]) -> None:
        self._ops.append(("zadd", key, mapping))

    def zcard(self, key: str) -> None:
        self._ops.append(("zcard", key))

    def expire(self, key: str, seconds: int) -> None:
        self._ops.append(("expire", key, seconds))

    async def execute(self) -> list[Any]:
        results = []
        for op in self._ops:
            if op[0] == "zremrangebyscore":
                _, key, lo, hi = op
                zset = self._redis._zsets.setdefault(key, {})
                to_del = [m for m, s in zset.items() if lo <= s <= hi]
                for m in to_del:
                    del zset[m]
                results.append(None)
            elif op[0] == "zadd":
                _, key, mapping = op
                zset = self._redis._zsets.setdefault(key, {})
                zset.update(mapping)
                results.append(None)
            elif op[0] == "zcard":
                _, key = op
                results.append(len(self._redis._zsets.get(key, {})))
            elif op[0] == "expire":
                results.append(True)
            else:
                results.append(None)
        return results


class FakeRedis:
    """Redis async en memoria para sesiones, idempotencia y rate limit."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[float | None, str]] = {}
        self._zsets: dict[str, dict[str, float]] = {}

    async def get(self, key: str) -> str | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if expires_at is not None and time.time() > expires_at:
            del self._store[key]
            return None
        return value

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self._store[key] = (time.time() + ttl, value)

    async def exists(self, key: str) -> int:
        val = await self.get(key)
        return 1 if val is not None else 0

    def pipeline(self) -> FakePipeline:
        return FakePipeline(self)

    async def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Datos de prueba Shopify
# ---------------------------------------------------------------------------

TEST_PHONE = "+573001234567"

MOCK_PRODUCTS = [
    {
        "id": 7001,
        "title": "Audífonos Sony WH-1000XM5",
        "price": 899_000,
        "stock": 12,
        "category": "Audio",
    },
    {
        "id": 7002,
        "title": "Samsung Galaxy Buds2 Pro",
        "price": 549_000,
        "stock": 8,
        "category": "Audio",
    },
    {
        "id": 7003,
        "title": "Apple AirPods Pro (2.ª gen)",
        "price": 999_000,
        "stock": 0,
        "category": "Audio",
    },
]

MOCK_CUSTOMER = {
    "id": 5001,
    "first_name": "Juan",
    "last_name": "Pérez",
    "email": "juan.perez@email.com",
    "phone": TEST_PHONE,
    "orders_count": 2,
    "total_spent": "1.448.000",
}

MOCK_ORDERS = {
    "#1042": {
        "id": 9001,
        "name": "#1042",
        "phone": TEST_PHONE,
        "financial_status": "paid",
        "fulfillment_status": "fulfilled",
        "total_price": "899.000",
        "currency": "COP",
        "created_at": "2026-06-10T14:30:00",
        "tracking": "Servientrega: 7348291028374",
        "line_items": [{"title": "Audífonos Sony WH-1000XM5", "quantity": 1, "price": "899.000"}],
    },
    "#1038": {
        "id": 9002,
        "name": "#1038",
        "phone": TEST_PHONE,
        "financial_status": "paid",
        "fulfillment_status": "unfulfilled",
        "total_price": "549.000",
        "currency": "COP",
        "created_at": "2026-06-20T09:15:00",
        "tracking": None,
        "line_items": [{"title": "Samsung Galaxy Buds2 Pro", "quantity": 1, "price": "549.000"}],
    },
}

# Respuestas RAG hardcodeadas (simulan ChromaDB)
RAG_RESPONSES: list[tuple[list[str], str]] = [
    (
        ["pasto", "envío", "envios", "nariño", "ciudades"],
        (
            "*Información encontrada:*\n\n"
            "📄 _politica_envios.txt_ (relevancia: 92%)\n"
            "Enviamos a *Pasto* y todo Nariño en 6 a 8 días hábiles vía "
            "*Coordinadora* o *Servientrega*.\n"
            "- Compras desde $150.000 COP: envío GRATIS a ciudades principales\n"
            "- Pasto (ciudad intermedia): tarifa estándar $12.000 COP\n"
            "- Seguimiento por guía al despachar tu pedido"
        ),
    ),
    (
        ["pago", "pse", "nequi", "garantía", "horario"],
        (
            "*Información encontrada:*\n\n"
            "📄 _preguntas_frecuentes.txt_ (relevancia: 88%)\n"
            "Aceptamos PSE, Nequi, Bancolombia y tarjetas Visa/Mastercard."
        ),
    ),
]

# ---------------------------------------------------------------------------
# Tracker global de nodos y tools
# ---------------------------------------------------------------------------


@dataclass
class TurnResult:
    turn: int
    message: str
    nodes: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    response: str = ""
    classification_retries: int = 0


@dataclass
class RunTracker:
    """Acumula métricas de toda la ejecución."""

    node_hits: dict[str, int] = field(default_factory=dict)
    tool_hits: dict[str, int] = field(default_factory=dict)
    total_classification_retries: int = 0
    turns: list[TurnResult] = field(default_factory=list)

    def record_node(self, name: str) -> None:
        self.node_hits[name] = self.node_hits.get(name, 0) + 1

    def record_tool(self, name: str) -> None:
        self.tool_hits[name] = self.tool_hits.get(name, 0) + 1


TRACKER = RunTracker()
TOOL_LOG: list[str] = []  # tools del turno actual


def _log_tool(name: str) -> None:
    TOOL_LOG.append(name)
    TRACKER.record_tool(name)


def _wrap_tool(name: str, fn: Callable) -> Callable:
    """Reservado por compatibilidad; el logging vive en cada mock_*."""
    return fn


# ---------------------------------------------------------------------------
# Mocks Shopify (texto legible WhatsApp)
# ---------------------------------------------------------------------------


def _fmt_cop(amount: int | str) -> str:
    if isinstance(amount, int):
        return f"${amount:,}".replace(",", ".") + " COP"
    return f"${amount} COP"


def mock_search_products(query: str, max_price: float | None = None, category: str | None = None) -> str:
    _log_tool("search_products")
    q = query.lower()
    matches = [p for p in MOCK_PRODUCTS if "sony" in q and "sony" in p["title"].lower() or "audífon" in q]
    if not matches and q:
        matches = [p for p in MOCK_PRODUCTS if any(w in p["title"].lower() for w in q.split())]
    if not matches:
        matches = MOCK_PRODUCTS

    if max_price is not None:
        matches = [p for p in matches if p["price"] <= max_price]

    lines = [f'*Resultados para "{query}"*\n']
    for p in matches[:3]:
        avail = "Disponible ✅" if p["stock"] > 0 else "Agotado ❌"
        lines.append(
            f"- *{p['title']}*\n"
            f"  Precio: {_fmt_cop(p['price'])}\n"
            f"  Estado: {avail} | ID: {p['id']}"
        )
    lines.append("\n_Pide el ID para ver más detalles._")
    return "\n".join(lines)


def mock_get_product_detail(product_id: str) -> str:
    _log_tool("get_product_detail")
    pid = int(product_id)
    p = next((x for x in MOCK_PRODUCTS if x["id"] == pid), MOCK_PRODUCTS[0])
    stock = "En stock ✅" if p["stock"] > 0 else "Agotado ❌"
    return (
        f"*{p['title']}*\n"
        f"Categoría: {p['category']}\n\n"
        f"Precio: {_fmt_cop(p['price'])}\n"
        f"Disponibilidad: {stock}\n"
        f"ID: {p['id']}"
    )


def mock_get_order_by_number(order_number: str, customer_phone: str) -> str:
    _log_tool("get_order_by_number")
    name = order_number if order_number.startswith("#") else f"#{order_number}"
    order = MOCK_ORDERS.get(name)
    if not order:
        return f"No encontré el pedido *{name}*. Revisa tu confirmación de compra."

    order_phone = order["phone"]
    if order_phone[-10:] != customer_phone[-10:]:
        return "Por tu seguridad, el teléfono no coincide con el registrado en el pedido."

    lines = [
        f"*Pedido {order['name']}*",
        f"Estado de pago: Pagado ✅",
        f"Estado de envío: {'Despachado' if order['fulfillment_status'] == 'fulfilled' else 'En preparación'}",
        f"Total: {_fmt_cop(order['total_price'])}",
        f"Fecha: {order['created_at'][:10]}",
        "",
        "*Productos:*",
        f"- {order['line_items'][0]['title']} x1",
    ]
    if order.get("tracking"):
        lines.extend(["", "*Rastreo:*", f"- {order['tracking']}"])
    lines.append(f"\n_ID interno del pedido: {order['id']}_")
    return "\n".join(lines)


def mock_get_customer_orders(phone: str) -> str:
    _log_tool("get_customer_orders")
    if phone[-10:] != TEST_PHONE[-10:]:
        return f"No encontré cuenta con teléfono *{phone}*."
    lines = [f"*Últimos pedidos de {MOCK_CUSTOMER['first_name']} {MOCK_CUSTOMER['last_name']}*\n"]
    for o in MOCK_ORDERS.values():
        status = "Despachado" if o["fulfillment_status"] == "fulfilled" else "En preparación"
        lines.append(f"- *{o['name']}* — {status} | {_fmt_cop(o['total_price'])}")
    lines.append(f"\n_ID de cliente: {MOCK_CUSTOMER['id']}_")
    return "\n".join(lines)


def mock_get_customer_by_phone(phone: str) -> str:
    _log_tool("get_customer_by_phone")
    if phone[-10:] != TEST_PHONE[-10:]:
        return f"No encontré cuenta con teléfono *{phone}*."
    c = MOCK_CUSTOMER
    return (
        f"*Cliente encontrado*\n"
        f"- Nombre: {c['first_name']} {c['last_name']}\n"
        f"- Email: {c['email']}\n"
        f"- Pedidos: {c['orders_count']}\n"
        f"- ID de cliente: {c['id']}"
    )


def mock_create_refund(order_id: str, reason: str, line_item_ids: list | None = None) -> str:
    _log_tool("create_refund")
    return (
        f"*Reembolso iniciado* ✅\n"
        f"- Pedido ID: {order_id}\n"
        f"- Motivo: {reason}\n"
        f"- Referencia: REF-{order_id}\n\n"
        "Recibirás confirmación por email. El reembolso tarda 5-10 días hábiles "
        "según tu banco o medio de pago."
    )


def mock_search_knowledge_base(query: str) -> str:
    _log_tool("search_knowledge_base")
    q = query.lower()
    for keywords, response in RAG_RESPONSES:
        if any(kw in q for kw in keywords):
            return response
    return "No encontré información confiable sobre esto en nuestra base de conocimiento."


# ---------------------------------------------------------------------------
# Mock LLM determinista (sin API key)
# ---------------------------------------------------------------------------


def _classify_intent(text: str) -> str:
    t = text.lower()
    if re.search(r"\b(hola|buenas|buenos|buen día)\b", t):
        return "saludo"
    if re.search(r"\b(hablar con|alguien|desastre|furioso|supervisor|humano)\b", t):
        return "escalada"
    if re.search(r"\b(devolv|reembolso|roto|defectuoso)\b", t):
        return "pedidos"
    if re.search(r"\b(pedido|#1042|#1038|orden|rastreo)\b", t):
        return "pedidos"
    if re.search(r"\b(sony|audífon|producto|precio|comprar)\b", t):
        return "ventas"
    if re.search(r"\b(envío|envios|pasto|pago|garantía|horario)\b", t):
        return "rag"
    return "rag"


class DeterministicTestLLM:
    """Simula Gemini para clasificación, validación, saludo y formateo."""

    async def ainvoke(self, messages: list) -> Any:
        from langchain_core.messages import AIMessage

        system = ""
        user = ""
        for m in messages:
            content = m.content if hasattr(m, "content") else m.get("content", "")
            role = getattr(m, "type", None) or m.get("role", "")
            is_system = role == "system" or (hasattr(m, "type") and m.type == "system")
            if is_system:
                if "clasificador" in content.lower() or "categoría" in content.lower():
                    system = content
                elif "Evalúa" in content or "valid" in content.lower():
                    system = "validator"
                elif "Formatea" in content:
                    system = "format"
                elif "escalada" in content.lower() or "asesor humano" in content.lower():
                    system = "escalation"
                elif "Saluda" in content or ("Sofía" in content and "clasificador" not in content.lower()):
                    system = "saludo"
            if role in ("human", "user") or (hasattr(m, "type") and m.type == "human"):
                if "Consulta:" not in content and "Respuesta propuesta:" not in content:
                    user = content
                elif "Respuesta propuesta:" in content:
                    user = content.split("Respuesta propuesta:")[-1].strip()

        if system == "validator":
            return AIMessage(content='{"valid": true, "reason": "Resuelve la consulta"}')

        if system == "format":
            # Texto a formatear: último mensaje humano del batch
            human_texts = []
            for m in messages:
                c = m.content if hasattr(m, "content") else m.get("content", "")
                r = getattr(m, "type", None) or m.get("role", "")
                if r in ("human", "user"):
                    human_texts.append(c)
            raw = human_texts[-1] if human_texts else user
            if not raw.startswith("*"):
                raw = raw.replace("Información encontrada:", "*Información encontrada:*")
            return AIMessage(content=raw)

        if system == "escalation":
            return AIMessage(
                content=(
                    "Lamento mucho lo que pasó con tu pedido 😔\n"
                    "Ya escalé tu caso a un *asesor humano* que te contactará "
                    "en máximo *24 horas hábiles* (lun-vie 8am-6pm)."
                )
            )

        if system == "saludo" or _classify_intent(user) == "saludo":
            return AIMessage(
                content=(
                    "¡Hola, buenas tardes! 😊 Soy *Sofía*, tu asistente virtual.\n"
                    "¿Te ayudo con productos, pedidos o envíos?"
                )
            )

        if "clasificador" in system.lower() or "categoría" in system.lower() or not system:
            return AIMessage(content=_classify_intent(user))

        return AIMessage(content="Con gusto te ayudo. ¿Puedes darme más detalle?")


def mock_create_agent(tools: list, system_prompt: str):
    """Agente ReAct simulado: invoca tools según palabras clave del mensaje."""

    tool_by_name = {}
    for t in tools:
        name = getattr(t, "name", None) or getattr(t, "__name__", "tool")
        tool_by_name[name] = t

    async def invoke_agent(user_message: str) -> str:
        text = user_message.lower()
        phone = TEST_PHONE
        if "teléfono whatsapp:" in text:
            match = re.search(r"\+?\d{10,13}", user_message)
            if match:
                phone = match.group(0)

        if "search_knowledge_base" in tool_by_name:
            query = user_message.split("\n")[-1] if "\n" in user_message else user_message
            fn = tool_by_name["search_knowledge_base"]
            return fn.invoke({"query": query}) if hasattr(fn, "invoke") else fn(query)

        if "search_products" in tool_by_name:
            if "sony" in text or "audífon" in text:
                fn = tool_by_name["search_products"]
                return fn.invoke({"query": "Sony audífonos"}) if hasattr(fn, "invoke") else fn("Sony audífonos")

        if "get_order_by_number" in tool_by_name:
            order_match = re.search(r"#\d{3,5}", user_message)
            if not order_match:
                order_match = re.search(r"pedido\s+#?(\d{3,5})", user_message, re.IGNORECASE)
                order_num = f"#{order_match.group(1)}" if order_match else "#1042"
            else:
                order_num = order_match.group(0)
            fn = tool_by_name["get_order_by_number"]
            args = {"order_number": order_num, "customer_phone": phone}
            return fn.invoke(args) if hasattr(fn, "invoke") else fn(**args)

        if "create_refund" in tool_by_name:
            order_id = "9001"
            reason = "Producto llegó dañado"
            if "roto" in text:
                reason = "Producto llegó roto/dañado"
            fn = tool_by_name["create_refund"]
            args = {"order_id": order_id, "reason": reason}
            return fn.invoke(args) if hasattr(fn, "invoke") else fn(**args)

        if "get_customer_by_phone" in tool_by_name:
            fn = tool_by_name["get_customer_by_phone"]
            return fn.invoke({"phone": phone}) if hasattr(fn, "invoke") else fn(phone)

        return "Procesé tu solicitud. ¿Necesitas algo más?"

    return invoke_agent


# ---------------------------------------------------------------------------
# Instrumentación del grafo
# ---------------------------------------------------------------------------

NODE_NAMES = [
    "classify_intent",
    "rag_node",
    "sales_node",
    "orders_node",
    "customers_node",
    "refunds_node",
    "escalation_node",
    "saludo_directo",
    "response_validator",
    "format_response",
]

TURN_NODES: list[str] = []


def _wrap_node(name: str, fn: Callable) -> Callable:
    async def wrapped(state: dict) -> dict:
        TURN_NODES.append(name)
        TRACKER.record_node(name)
        return await fn(state)

    wrapped.__name__ = name
    return wrapped


def _stub_redis() -> None:
    """Evita dependencia de redis instalado durante pruebas locales."""
    import types

    fake = FakeRedis()

    class _RedisAsyncStub:
        @staticmethod
        def from_url(_url: str, **kwargs):
            return fake

    asyncio_mod = types.ModuleType("redis.asyncio")
    asyncio_mod.from_url = _RedisAsyncStub.from_url
    asyncio_mod.Redis = FakeRedis

    redis_mod = types.ModuleType("redis")
    redis_mod.asyncio = asyncio_mod

    sys.modules.setdefault("redis", redis_mod)
    sys.modules.setdefault("redis.asyncio", asyncio_mod)


def _stub_agents_base() -> None:
    """Evita importar langgraph.prebuilt; inyecta LLM/agente de prueba."""
    if os.environ.get("USE_REAL_LLM", "").lower() in ("1", "true", "yes"):
        return

    import types

    stub = types.ModuleType("agents.base")
    stub.create_llm = lambda: DeterministicTestLLM()
    stub.create_agent = mock_create_agent
    sys.modules["agents.base"] = stub


def _apply_patches() -> None:
    """Parchea dependencias externas y resetea singletons del grafo."""
    _stub_redis()
    _stub_agents_base()

    import graph.builder as builder_mod
    import graph.nodes as nodes_mod
    import memory.session as session_mod
    from langchain_core.tools import tool

    # Reset singletons
    builder_mod._compiled_graph = None
    for attr in ("_rag_agent", "_sales_agent", "_orders_agent", "_customers_agent", "_refunds_agent"):
        setattr(nodes_mod, attr, None)

    fake_redis = FakeRedis()

    async def _fake_get_redis():
        return fake_redis

    session_mod.get_redis = _fake_get_redis
    session_mod.close_redis = fake_redis.close

    # Tools mockeadas con @tool para LangChain
    @tool
    def search_products(query: str, max_price: float | None = None, category: str | None = None) -> str:
        """Busca productos en Shopify por nombre, categoría o precio máximo."""
        return mock_search_products(query, max_price, category)

    @tool
    def get_product_detail(product_id: str) -> str:
        """Retorna detalle completo de un producto."""
        return mock_get_product_detail(product_id)

    @tool
    def get_order_by_number(order_number: str, customer_phone: str) -> str:
        """Busca un pedido por número validando teléfono."""
        return mock_get_order_by_number(order_number, customer_phone)

    @tool
    def get_customer_orders(phone: str) -> str:
        """Retorna los últimos pedidos de un cliente."""
        return mock_get_customer_orders(phone)

    @tool
    def get_customer_by_phone(phone: str) -> str:
        """Busca un cliente por teléfono."""
        return mock_get_customer_by_phone(phone)

    @tool
    def create_refund(order_id: str, reason: str, line_item_ids: list | None = None) -> str:
        """Crea solicitud de reembolso."""
        return mock_create_refund(order_id, reason, line_item_ids)

    @tool
    def search_knowledge_base(query: str) -> str:
        """Busca en la base de conocimiento."""
        return mock_search_knowledge_base(query)

    # Parchear módulos
    import tools.knowledge_base as kb_mod
    import tools.shopify as shopify_mod
    import tools.whatsapp as wa_mod

    shopify_mod.search_products = search_products
    shopify_mod.get_product_detail = get_product_detail
    shopify_mod.get_order_by_number = get_order_by_number
    shopify_mod.get_customer_orders = get_customer_orders
    shopify_mod.get_customer_by_phone = get_customer_by_phone
    shopify_mod.create_refund = create_refund
    kb_mod.search_knowledge_base = search_knowledge_base

    async def _noop_escalation(**kwargs):
        pass

    wa_mod.notify_escalation = _noop_escalation
    wa_mod.send_template = _noop_escalation

    nodes_mod.search_knowledge_base = search_knowledge_base
    nodes_mod.search_products = search_products
    nodes_mod.get_product_detail = get_product_detail
    nodes_mod.get_order_by_number = get_order_by_number
    nodes_mod.get_customer_orders = get_customer_orders
    nodes_mod.get_customer_by_phone = get_customer_by_phone
    nodes_mod.create_refund = create_refund

    # Envolver nodos para tracking y sincronizar refs en builder (ya importado arriba)
    for node_name in NODE_NAMES:
        original = getattr(nodes_mod, node_name)
        wrapped = _wrap_node(node_name, original)
        setattr(nodes_mod, node_name, wrapped)
        setattr(builder_mod, node_name, wrapped)


# ---------------------------------------------------------------------------
# Conversaciones de prueba
# ---------------------------------------------------------------------------

TEST_MESSAGES = [
    "Hola buenas tardes",
    "¿Hacen envíos a Pasto?",
    "Quiero ver audífonos Sony",
    "¿Cuánto vale el pedido #1042?",
    "Quiero devolver ese pedido, me llegó roto",
    "Esto es un desastre, necesito hablar con alguien ya",
]


def _print_turn(result: TurnResult) -> None:
    sep = "-" * 60
    print(f"\n{sep}")
    print(f"TURNO {result.turn}: \"{result.message}\"")
    print(sep)
    print(f"  Nodos visitados : {' → '.join(result.nodes) or '(ninguno)'}")
    print(f"  Tools llamadas  : {', '.join(result.tools) if result.tools else '(ninguna)'}")
    if result.classification_retries:
        print(f"  Re-clasificaciones en este turno: {result.classification_retries}")
    print(f"\n  Respuesta final:\n")
    for line in result.response.split("\n"):
        print(f"    {line}")
    print()


def _count_classify_retries(nodes: list[str]) -> int:
    """Cuenta reentradas a classify_intent después de la primera."""
    if not nodes:
        return 0
    return max(0, nodes.count("classify_intent") - 1)


async def run_tests() -> None:
    # Compatibilidad langchain/langchain-core desalineados en el entorno local
    try:
        import langchain

        if not hasattr(langchain, "debug"):
            langchain.debug = False  # type: ignore[attr-defined]
        if not hasattr(langchain, "verbose"):
            langchain.verbose = False  # type: ignore[attr-defined]
    except ImportError:
        pass

    from config import get_settings

    get_settings.cache_clear()
    _apply_patches()

    from graph.builder import build_graph
    from langchain_core.messages import HumanMessage
    from memory.session import append_user_message, load_state, save_state

    graph = build_graph().compile()

    state: dict = {
        "messages": [],
        "phone": TEST_PHONE,
        "intent": "",
        "shopify_customer_id": "",
        "attempts": 0,
        "requires_human": False,
        "final_response": "",
        "message_id": "",
        "needs_refund": False,
    }

    print("=" * 60)
    print("  TEST LOCAL — Grafo LangGraph (ecommerce_swarm)")
    print("  Mocks: Redis | Shopify | ChromaDB | LLM determinista")
    print("  (export USE_REAL_LLM=1 para usar Gemini real si tienes API key)")
    print("=" * 60)

    for i, message in enumerate(TEST_MESSAGES, start=1):
        global TURN_NODES, TOOL_LOG
        TURN_NODES = []
        TOOL_LOG = []

        state = append_user_message(state, message)
        state["message_id"] = f"test_msg_{i}"
        state["phone"] = TEST_PHONE

        result_state = await graph.ainvoke(state)
        state = result_state

        await save_state(TEST_PHONE, state)

        retries = _count_classify_retries(TURN_NODES)
        TRACKER.total_classification_retries += retries

        turn = TurnResult(
            turn=i,
            message=message,
            nodes=list(TURN_NODES),
            tools=list(TOOL_LOG),
            response=state.get("final_response", "(sin respuesta)"),
            classification_retries=retries,
        )
        TRACKER.turns.append(turn)
        _print_turn(turn)

    _print_summary()


def _print_summary() -> None:
    print("=" * 60)
    print("  RESUMEN DE EJECUCIÓN")
    print("=" * 60)

    print("\n📊 Turnos resueltos por nodo especializado (visitas totales):")
    specialized = [
        "saludo_directo",
        "rag_node",
        "sales_node",
        "orders_node",
        "refunds_node",
        "customers_node",
        "escalation_node",
        "response_validator",
        "format_response",
        "classify_intent",
    ]
    for node in specialized:
        count = TRACKER.node_hits.get(node, 0)
        if count:
            bar = "█" * min(count, 20)
            print(f"  {node:22} {count:3}  {bar}")

    print("\n🔧 Tools invocadas:")
    if TRACKER.tool_hits:
        for tool, count in sorted(TRACKER.tool_hits.items()):
            print(f"  {tool}: {count}x")
    else:
        print("  (ninguna)")

    print(f"\n🔄 Re-clasificaciones totales (classify_intent reentrante): {TRACKER.total_classification_retries}")

    escalated = sum(1 for t in TRACKER.turns if "escalation_node" in t.nodes)
    print(f"⚠️  Turnos con escalada humana: {escalated}")

    print("\n✅ Prueba completada — 6/6 turnos procesados")
    print("=" * 60)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    try:
        asyncio.run(run_tests())
    except KeyboardInterrupt:
        print("\nInterrumpido.")
        sys.exit(130)
    except Exception as exc:
        print(f"\n❌ Error: {exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
