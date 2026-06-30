"""Infraestructura compartida de mocks para evaluación y tests locales."""

from __future__ import annotations

import re
import sys
import types
from typing import Any, Callable

from eval.tracer import EvalTracer, get_tool_log, reset_tool_log

TEST_PHONE = "+573001234567"

MOCK_PRODUCTS = [
    {"id": 7001, "title": "Audífonos Sony WH-1000XM5", "price": 899_000, "stock": 12, "category": "Audio"},
    {"id": 7002, "title": "Samsung Galaxy Buds2 Pro", "price": 549_000, "stock": 8, "category": "Audio"},
    {"id": 7003, "title": "Apple AirPods Pro (2.ª gen)", "price": 999_000, "stock": 0, "category": "Audio"},
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
        "refunded": False,
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
        "refunded": False,
    },
}

RAG_RESPONSES: list[tuple[list[str], str]] = [
    (
        ["pasto", "envío", "envios", "nariño", "ciudades", "coordinadora", "servientrega"],
        (
            "*Información encontrada:*\nEnviamos a *Pasto* en 6-8 días hábiles vía Coordinadora/Servientrega.\n"
            "- Compras desde $150.000 COP: envío GRATIS\n- Pasto: tarifa $12.000 COP"
        ),
    ),
    (
        ["devoluc", "reembolso", "plazo", "30"],
        "*Información encontrada:*\nPlazo de *30 días* para devoluciones. Producto sin usar en empaque original.",
    ),
    (
        ["garantía", "garantia", "electronic"],
        "*Información encontrada:*\nElectrónicos: *12 meses* de garantía por defectos de fábrica.",
    ),
    (
        ["horario", "atención", "humanos", "sábado"],
        "*Información encontrada:*\nAgentes humanos: lun-vie 8am-6pm, sáb 9am-1pm. Bot 24/7.",
    ),
    (
        ["pse", "nequi", "bancolombia", "pago", "pagos", "tarjeta"],
        "*Información encontrada:*\nAceptamos PSE, Nequi, Daviplata, Bancolombia y tarjetas Visa/Mastercard.",
    ),
    (
        ["gratis", "150", "envío gratis"],
        "*Información encontrada:*\nEnvío GRATIS en compras desde $150.000 COP a ciudades principales.",
    ),
]

NODE_NAMES = [
    "classify_intent", "rag_node", "sales_node", "orders_node", "customers_node",
    "refunds_node", "escalation_node", "saludo_directo", "response_validator", "format_response",
]

SPECIALIZED_NODES = {
    "rag_node", "sales_node", "orders_node", "customers_node",
    "refunds_node", "escalation_node", "saludo_directo",
}


def _log_tool(name: str, params: dict | None = None) -> None:
    get_tool_log().append({"name": name, "params": params or {}})


def _fmt_cop(amount: int | str) -> str:
    if isinstance(amount, int):
        return f"${amount:,}".replace(",", ".") + " COP"
    return f"${amount} COP"


def mock_search_products(query: str, max_price: float | None = None, category: str | None = None) -> str:
    _log_tool("search_products", {"query": query, "max_price": max_price, "category": category})
    q = query.lower()
    matches = list(MOCK_PRODUCTS)
    if "sony" in q:
        matches = [p for p in matches if "sony" in p["title"].lower()]
    if category:
        matches = [p for p in matches if category.lower() in p["category"].lower()]
    if max_price is not None:
        matches = [p for p in matches if p["price"] <= max_price]
    lines = [f'*Resultados para "{query}"*\n']
    for p in matches[:3]:
        avail = "Disponible" if p["stock"] > 0 else "Agotado"
        lines.append(f"- *{p['title']}* — {_fmt_cop(p['price'])} ({avail}) | ID: {p['id']}")
    return "\n".join(lines)


def mock_get_product_detail(product_id: str) -> str:
    _log_tool("get_product_detail", {"product_id": product_id})
    pid = int(product_id)
    p = next((x for x in MOCK_PRODUCTS if x["id"] == pid), MOCK_PRODUCTS[0])
    return f"*{p['title']}* — {_fmt_cop(p['price'])} | ID: {p['id']}"


def mock_get_order_by_number(order_number: str, customer_phone: str) -> str:
    _log_tool("get_order_by_number", {"order_number": order_number, "customer_phone": customer_phone})
    name = order_number if order_number.startswith("#") else f"#{order_number}"
    order = MOCK_ORDERS.get(name)
    if not order:
        return f"No encontré el pedido *{name}*."
    if order["phone"][-10:] != customer_phone[-10:]:
        return "Por seguridad, el teléfono no coincide con el pedido."
    if order.get("refunded"):
        return "Este pedido ya fue reembolsado por completo."
    lines = [
        f"*Pedido {order['name']}*",
        f"Total: {_fmt_cop(order['total_price'])}",
        f"Estado envío: {'Despachado' if order['fulfillment_status'] == 'fulfilled' else 'En preparación'}",
    ]
    if order.get("tracking"):
        lines.append(f"Rastreo: {order['tracking']}")
    lines.append(f"ID interno: {order['id']}")
    return "\n".join(lines)


def mock_get_customer_orders(phone: str) -> str:
    _log_tool("get_customer_orders", {"phone": phone})
    if phone[-10:] != TEST_PHONE[-10:]:
        return f"No encontré cuenta con teléfono *{phone}*."
    lines = ["*Últimos pedidos:*"]
    for o in MOCK_ORDERS.values():
        lines.append(f"- {o['name']} — {_fmt_cop(o['total_price'])}")
    return "\n".join(lines)


def mock_get_customer_by_phone(phone: str) -> str:
    _log_tool("get_customer_by_phone", {"phone": phone})
    if phone[-10:] != TEST_PHONE[-10:]:
        return f"No encontré cuenta con teléfono *{phone}*."
    c = MOCK_CUSTOMER
    return (
        f"*Cliente:* {c['first_name']} {c['last_name']}\n"
        f"Email: {c['email']}\nID de cliente: {c['id']}"
    )


def mock_create_refund(order_id: str, reason: str, line_item_ids: list | None = None) -> str:
    _log_tool("create_refund", {"order_id": order_id, "reason": reason})
    return f"*Reembolso iniciado* para pedido {order_id}. Motivo: {reason}"


def mock_search_knowledge_base(query: str) -> str:
    _log_tool("search_knowledge_base", {"query": query})
    q = query.lower()
    for keywords, response in RAG_RESPONSES:
        if any(kw in q for kw in keywords):
            return response
    return "No encontré información confiable sobre esto en nuestra base de conocimiento."


def _classify_intent(text: str) -> str:
    t = text.lower()
    if re.search(r"\b(hola|buenas|buenos)\b", t):
        return "saludo"
    if re.search(r"\b(hablar con|humano|persona|supervisor|desastre|furioso|harto|nadie me ayuda)\b", t):
        return "escalada"
    # Política de devoluciones (sin pedido concreto) → RAG
    if re.search(r"devolv\w*", t) and re.search(
        r"\b(días|dias|plazo|política|cuántos|cuantos)\b", t
    ):
        return "rag"
    if re.search(r"devolv\w*|reembolso|reembols\w*", t):
        return "pedidos"
    if re.search(r"\b(pedido|#\d|orden|rastreo|tracking|cuándo|cuando|últimos pedidos|mis pedidos)\b", t):
        return "pedidos"
    if re.search(r"\b(cuenta|email|perfil|cliente|registrada|teléfono)\b", t) and re.search(
        r"\b(cuenta|cliente|perfil)\b", t
    ):
        return "clientes"
    if re.search(
        r"\b(sony|audífon|producto|precio|comprar|headphone|catálogo|pesos|máximo|categoría|audio)\b", t
    ) or (re.search(r"\d{5,}", t) and not re.search(r"\+?\d{10,}", t)):
        return "ventas"
    if re.search(r"\b(envío|envios|pasto|pago|garantía|horario|pse|nequi|servientrega|coordinadora)\b", t):
        return "rag"
    return "rag"


class DeterministicTestLLM:
    async def ainvoke(self, messages: list | str) -> Any:
        from langchain_core.messages import AIMessage

        if isinstance(messages, str):
            text = messages
            system = "judge" if "evaluador experto" in text.lower() else ""
            user = text
            if system == "judge":
                return AIMessage(
                    content='{"scores": {"resolucion": 3, "precision": 3, "tono": 2, "formato": 2}, '
                    '"total": 10, "feedback": "Respuesta adecuada (mock judge)."}'
                )
            return AIMessage(content=_classify_intent(text) if not system else text[:200])

        system = ""
        user = ""
        for m in messages:
            content = m.content if hasattr(m, "content") else m.get("content", "")
            role = getattr(m, "type", None) or m.get("role", "")
            is_system = role == "system" or (hasattr(m, "type") and m.type == "system")
            if is_system:
                if "clasificador" in content.lower() or "categoría" in content.lower():
                    system = "classifier"
                elif "Evalúa" in content:
                    system = "validator"
                elif "Formatea" in content:
                    system = "format"
                elif "escalada" in content.lower() or "asesor humano" in content.lower():
                    system = "escalation"
                elif "Saluda" in content or ("Sofía" in content and "clasificador" not in content.lower()):
                    system = "saludo"
                elif "evaluador experto" in content.lower():
                    system = "judge"
            if role in ("human", "user"):
                if "Respuesta a evaluar:" in content:
                    user = content
                elif "Consulta:" not in content:
                    user = content

        if system == "validator":
            return AIMessage(content='{"valid": true, "reason": "ok"}')
        if system == "format":
            texts = [
                (m.content if hasattr(m, "content") else m.get("content", ""))
                for m in messages
                if (getattr(m, "type", None) or m.get("role", "")) in ("human", "user")
            ]
            return AIMessage(content=texts[-1] if texts else user)
        if system == "escalation":
            return AIMessage(content="Escalé tu caso. Un asesor te contactará en 24h hábiles.")
        if system == "saludo":
            return AIMessage(content="¡Hola! Soy *Sofía*. ¿En qué te ayudo?")
        if system == "classifier" or system == "":
            return AIMessage(content=_classify_intent(user))
        if system == "judge":
            return AIMessage(
                content='{"scores": {"resolucion": 3, "precision": 3, "tono": 2, "formato": 2}, '
                '"total": 10, "feedback": "Respuesta adecuada (mock judge)."}'
            )
        return AIMessage(content="Con gusto te ayudo.")


def mock_create_agent(tools: list, system_prompt: str):
    tool_by_name = {}
    for t in tools:
        name = getattr(t, "name", None)
        if not name:
            name = getattr(t, "__name__", str(t))
        tool_by_name[name] = t

    async def invoke_agent(user_message: str) -> str:
        text = user_message.lower()
        phone = TEST_PHONE
        m = re.search(r"\+?\d{10,13}", user_message)
        if m:
            phone = m.group(0)

        if "search_knowledge_base" in tool_by_name:
            q = user_message.split("\n")[-1].strip()
            return tool_by_name["search_knowledge_base"].invoke({"query": q})

        if "search_products" in tool_by_name:
            q = "Sony audífonos" if "sony" in text or "audífon" in text or "headphone" in text else "productos"
            mp = 600_000 if "600" in text or "600000" in text else None
            cat = "Audio" if "audio" in text or "categoría" in text else None
            return tool_by_name["search_products"].invoke({"query": q, "max_price": mp, "category": cat})

        if "get_product_detail" in tool_by_name:
            pid = "7001" if "sony" in text else "7002"
            m2 = re.search(r"\b700[123]\b", user_message)
            if m2:
                pid = m2.group(0)
            return tool_by_name["get_product_detail"].invoke({"product_id": pid})

        if "get_customer_orders" in tool_by_name and re.search(
            r"\b(mis pedidos|últimos pedidos|historial)\b", text
        ):
            return tool_by_name["get_customer_orders"].invoke({"phone": phone})

        if "get_order_by_number" in tool_by_name and re.search(r"#\d{3,5}", user_message):
            order_num = re.search(r"#\d{3,5}", user_message).group(0)
            return tool_by_name["get_order_by_number"].invoke(
                {"order_number": order_num, "customer_phone": phone}
            )

        if "get_customer_orders" in tool_by_name:
            return tool_by_name["get_customer_orders"].invoke({"phone": phone})

        if "get_customer_by_phone" in tool_by_name:
            return tool_by_name["get_customer_by_phone"].invoke({"phone": phone})

        if "create_refund" in tool_by_name:
            return tool_by_name["create_refund"].invoke(
                {"order_id": "9001", "reason": "Producto dañado"}
            )
        return "Procesado."

    return invoke_agent


class FakeRedis:
    def __init__(self) -> None:
        self._store: dict = {}
        self._zsets: dict = {}

    async def get(self, key: str):
        return self._store.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self._store[key] = value

    async def exists(self, key: str) -> int:
        return 1 if key in self._store else 0

    def pipeline(self):
        return self

    async def zremrangebyscore(self, *a, **k):
        return None

    async def zadd(self, *a, **k):
        return None

    async def zcard(self, *a, **k):
        return 1

    async def expire(self, *a, **k):
        return True

    async def execute(self):
        return [None, None, 1, True]

    async def close(self) -> None:
        pass


def _stub_redis() -> None:
    fake = FakeRedis()

    class _Stub:
        @staticmethod
        def from_url(*a, **k):
            return fake

    asyncio_mod = types.ModuleType("redis.asyncio")
    asyncio_mod.from_url = _Stub.from_url
    asyncio_mod.Redis = FakeRedis
    redis_mod = types.ModuleType("redis")
    redis_mod.asyncio = asyncio_mod
    sys.modules.setdefault("redis", redis_mod)
    sys.modules.setdefault("redis.asyncio", asyncio_mod)


def _stub_agents_base() -> None:
    stub = types.ModuleType("agents.base")
    stub.create_llm = lambda: DeterministicTestLLM()
    stub.create_agent = mock_create_agent
    sys.modules["agents.base"] = stub


_patches_applied = False
_nodes_wrapped = False
_current_tracer: EvalTracer | None = None


def set_current_tracer(tracer: EvalTracer | None) -> None:
    global _current_tracer
    _current_tracer = tracer


def apply_eval_patches() -> None:
    global _patches_applied
    if _patches_applied:
        return

    try:
        import langchain

        if not hasattr(langchain, "debug"):
            langchain.debug = False  # type: ignore
        if not hasattr(langchain, "verbose"):
            langchain.verbose = False  # type: ignore
    except ImportError:
        pass

    _stub_redis()
    _stub_agents_base()

    import graph.builder as builder_mod
    import graph.nodes as nodes_mod
    import memory.session as session_mod
    from langchain_core.tools import tool

    fake = FakeRedis()

    async def _fake_get_redis():
        return fake

    session_mod.get_redis = _fake_get_redis
    session_mod.close_redis = fake.close

    @tool
    def search_products(query: str, max_price: float | None = None, category: str | None = None) -> str:
        """Busca productos."""
        return mock_search_products(query, max_price, category)

    @tool
    def get_product_detail(product_id: str) -> str:
        """Detalle producto."""
        return mock_get_product_detail(product_id)

    @tool
    def get_order_by_number(order_number: str, customer_phone: str) -> str:
        """Busca pedido."""
        return mock_get_order_by_number(order_number, customer_phone)

    @tool
    def get_customer_orders(phone: str) -> str:
        """Pedidos cliente."""
        return mock_get_customer_orders(phone)

    @tool
    def get_customer_by_phone(phone: str) -> str:
        """Busca cliente."""
        return mock_get_customer_by_phone(phone)

    @tool
    def create_refund(order_id: str, reason: str, line_item_ids: list | None = None) -> str:
        """Crea reembolso."""
        return mock_create_refund(order_id, reason, line_item_ids)

    @tool
    def search_knowledge_base(query: str) -> str:
        """Busca KB."""
        return mock_search_knowledge_base(query)

    import tools.knowledge_base as kb_mod
    import tools.shopify as shopify_mod
    import tools.whatsapp as wa_mod

    for name, fn in [
        ("search_products", search_products),
        ("get_product_detail", get_product_detail),
        ("get_order_by_number", get_order_by_number),
        ("get_customer_orders", get_customer_orders),
        ("get_customer_by_phone", get_customer_by_phone),
        ("create_refund", create_refund),
    ]:
        setattr(shopify_mod, name, fn)
        setattr(nodes_mod, name, fn)
    kb_mod.search_knowledge_base = search_knowledge_base
    nodes_mod.search_knowledge_base = search_knowledge_base

    async def _noop_escalation(**kwargs):
        pass

    async def _noop_template(**kwargs):
        return None

    wa_mod.notify_escalation = _noop_escalation
    wa_mod.send_template = _noop_template

    builder_mod._compiled_graph = None
    for attr in ("_rag_agent", "_sales_agent", "_orders_agent", "_customers_agent", "_refunds_agent"):
        setattr(nodes_mod, attr, None)

    _patches_applied = True


def wrap_nodes_for_tracing() -> None:
    global _nodes_wrapped
    if _nodes_wrapped:
        return
    import graph.builder as builder_mod
    import graph.nodes as nodes_mod

    for node_name in NODE_NAMES:
        original = getattr(nodes_mod, node_name)

        async def wrapped(state, n=node_name, orig=original):
            if _current_tracer:
                _current_tracer.record_node(n)
            return await orig(state)

        setattr(nodes_mod, node_name, wrapped)
        setattr(builder_mod, node_name, wrapped)
    _nodes_wrapped = True


def build_eval_graph(tracer: EvalTracer | None = None):
    apply_eval_patches()
    wrap_nodes_for_tracing()
    set_current_tracer(tracer)
    from graph.builder import build_graph
    return build_graph().compile()
