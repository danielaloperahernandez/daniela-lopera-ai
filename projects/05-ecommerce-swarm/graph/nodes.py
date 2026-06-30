"""
Nodos del grafo LangGraph.
Cada nodo recibe ConversationState y retorna un dict con las claves a actualizar.
"""

import json
import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from agents.base import create_agent, create_llm
from agents.prompts import (
    CUSTOMERS_PROMPT,
    ESCALATION_PROMPT,
    ORDERS_PROMPT,
    RAG_PROMPT,
    REFUNDS_PROMPT,
    SALES_PROMPT,
    SALUDO_PROMPT,
    VALIDATOR_PROMPT,
)
from graph.state import ConversationState
from tools.knowledge_base import search_knowledge_base
from tools.shopify import (
    create_refund,
    get_customer_by_phone,
    get_customer_orders,
    get_order_by_number,
    get_product_detail,
    search_products,
)

# --- Agentes especializados (lazy: se crean una sola vez por proceso) ---

_rag_agent = None
_sales_agent = None
_orders_agent = None
_customers_agent = None
_refunds_agent = None


def _get_rag_agent():
    global _rag_agent
    if _rag_agent is None:
        _rag_agent = create_agent([search_knowledge_base], RAG_PROMPT)
    return _rag_agent


def _get_sales_agent():
    global _sales_agent
    if _sales_agent is None:
        _sales_agent = create_agent(
            [search_products, get_product_detail], SALES_PROMPT
        )
    return _sales_agent


def _get_orders_agent():
    global _orders_agent
    if _orders_agent is None:
        _orders_agent = create_agent(
            [get_order_by_number, get_customer_orders], ORDERS_PROMPT
        )
    return _orders_agent


def _get_customers_agent():
    global _customers_agent
    if _customers_agent is None:
        _customers_agent = create_agent([get_customer_by_phone], CUSTOMERS_PROMPT)
    return _customers_agent


def _get_refunds_agent():
    global _refunds_agent
    if _refunds_agent is None:
        _refunds_agent = create_agent([create_refund], REFUNDS_PROMPT)
    return _refunds_agent


def _last_user_text(state: ConversationState) -> str:
    """Extrae el texto del último mensaje humano del historial."""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            return msg.content
        if isinstance(msg, dict) and msg.get("role") == "user":
            return msg["content"]
    return ""


def _conversation_context(state: ConversationState, max_turns: int = 6) -> str:
    """Concatena los últimos turnos para dar contexto al agente."""
    lines = []
    for msg in state["messages"][-max_turns:]:
        if isinstance(msg, HumanMessage):
            lines.append(f"Cliente: {msg.content}")
        elif isinstance(msg, AIMessage):
            lines.append(f"Asistente: {msg.content}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# NODO 1: classify_intent
# ---------------------------------------------------------------------------


async def classify_intent(state: ConversationState) -> dict[str, Any]:
    """
    Clasifica la intención del usuario con Gemini.
    Detecta también si hay mención de devolución/reembolso para routing posterior.
    """
    from agents.prompts import CLASSIFIER_PROMPT

    user_text = _last_user_text(state)
    llm = create_llm()

    response = await llm.ainvoke(
        [
            {"role": "system", "content": CLASSIFIER_PROMPT},
            {"role": "user", "content": user_text},
        ]
    )
    intent = response.content.strip().lower()

    valid_intents = {
        "saludo",
        "rag",
        "ventas",
        "pedidos",
        "clientes",
        "escalada",
        "devolucion",
    }
    if intent not in valid_intents:
        # Fallback heurístico si el LLM no devuelve una categoría exacta
        intent = _heuristic_intent(user_text)

    refund_keywords = re.search(
        r"\b(devoluci[oó]n|reembolso|devolver|devuelv|cambio de producto)\b",
        user_text,
        re.IGNORECASE,
    )
    needs_refund = bool(refund_keywords) or intent == "devolucion"

    # Preguntas de política (plazo, cómo devolver) no deben forzarse a pedidos
    is_policy_question = bool(
        re.search(r"\b(días|dias|plazo|política|cuántos|cuantos|cómo|como)\b", user_text, re.IGNORECASE)
    )
    if needs_refund and intent not in ("escalada", "devolucion", "rag") and not is_policy_question:
        intent = "pedidos"

    return {"intent": intent, "needs_refund": needs_refund}


def _heuristic_intent(text: str) -> str:
    text_lower = text.lower()
    if re.search(r"\b(hola|buenos|buenas|gracias|adiós|chao)\b", text_lower):
        return "saludo"
    if re.search(r"\b(pedido|orden|tracking|rastreo|envío)\b", text_lower):
        return "pedidos"
    if re.search(r"\b(producto|precio|comprar|catálogo)\b", text_lower):
        return "ventas"
    if re.search(r"\b(devoluci|reembolso)\b", text_lower) and re.search(
        r"\b(días|dias|plazo|política|cuántos|cuantos)\b", text_lower
    ):
        return "rag"
    if re.search(r"\b(devoluci|reembolso)\b", text_lower):
        return "pedidos"
    if re.search(r"\b(cuenta|perfil|mis datos)\b", text_lower):
        return "clientes"
    if re.search(r"\b(humano|persona|supervisor|abogado)\b", text_lower):
        return "escalada"
    return "rag"


# ---------------------------------------------------------------------------
# NODOS ESPECIALIZADOS
# ---------------------------------------------------------------------------


async def rag_node(state: ConversationState) -> dict[str, Any]:
    agent = _get_rag_agent()
    context = _conversation_context(state)
    response = await agent(context)
    return {"final_response": response}


async def sales_node(state: ConversationState) -> dict[str, Any]:
    agent = _get_sales_agent()
    context = _conversation_context(state)
    response = await agent(context)
    return {"final_response": response}


async def orders_node(state: ConversationState) -> dict[str, Any]:
    agent = _get_orders_agent()
    phone = state.get("phone", "")
    context = f"Teléfono WhatsApp del cliente: {phone}\n\n{_conversation_context(state)}"
    response = await agent(context)
    return {"final_response": response}


async def customers_node(state: ConversationState) -> dict[str, Any]:
    agent = _get_customers_agent()
    phone = state.get("phone", "")
    context = f"Teléfono WhatsApp: {phone}\n\n{_conversation_context(state)}"
    response = await agent(context)

    # Intentar extraer customer_id del resultado para sesiones futuras
    customer_id = ""
    match = re.search(r"ID de cliente:\s*(\d+)", response, re.IGNORECASE)
    if match:
        customer_id = match.group(1)

    update: dict[str, Any] = {"final_response": response}
    if customer_id:
        update["shopify_customer_id"] = customer_id
    return update


async def refunds_node(state: ConversationState) -> dict[str, Any]:
    agent = _get_refunds_agent()
    phone = state.get("phone", "")
    context = f"Teléfono WhatsApp: {phone}\n\n{_conversation_context(state)}"
    response = await agent(context)
    return {"final_response": response}


async def escalation_node(state: ConversationState) -> dict[str, Any]:
    """Crea ticket de escalada y prepara mensaje al usuario."""
    from tools.whatsapp import notify_escalation

    user_text = _last_user_text(state)
    phone = state.get("phone", "")

    await notify_escalation(phone=phone, message=user_text, intent=state.get("intent", ""))

    llm = create_llm()
    response = await llm.ainvoke(
        [
            {"role": "system", "content": ESCALATION_PROMPT},
            {"role": "user", "content": user_text},
        ]
    )
    return {
        "final_response": response.content,
        "requires_human": True,
    }


async def saludo_directo(state: ConversationState) -> dict[str, Any]:
    llm = create_llm()
    user_text = _last_user_text(state)
    response = await llm.ainvoke(
        [
            {"role": "system", "content": SALUDO_PROMPT},
            {"role": "user", "content": user_text},
        ]
    )
    return {"final_response": response.content}


# ---------------------------------------------------------------------------
# NODO 8: response_validator
# ---------------------------------------------------------------------------


async def response_validator(state: ConversationState) -> dict[str, Any]:
    """
    Verifica que final_response resuelve la consulta del usuario.
    Incrementa attempts si la respuesta no es válida.
    """
    user_text = _last_user_text(state)
    candidate = state.get("final_response", "")

    if not candidate:
        return {"attempts": state.get("attempts", 0) + 1}

    llm = create_llm()
    response = await llm.ainvoke(
        [
            {"role": "system", "content": VALIDATOR_PROMPT},
            {
                "role": "user",
                "content": f"Consulta: {user_text}\n\nRespuesta propuesta: {candidate}",
            },
        ]
    )

    try:
        # Extraer JSON aunque venga envuelto en markdown
        raw = response.content.strip()
        if "```" in raw:
            raw = re.search(r"\{.*\}", raw, re.DOTALL)
            raw = raw.group(0) if raw else '{"valid": true}'
        verdict = json.loads(raw)
        valid = verdict.get("valid", True)
    except (json.JSONDecodeError, AttributeError):
        valid = True  # ante duda, aceptar para no bloquear al usuario

    if valid:
        return {"attempts": 0}

    new_attempts = state.get("attempts", 0) + 1
    return {"attempts": new_attempts}


# ---------------------------------------------------------------------------
# NODO 9: format_response
# ---------------------------------------------------------------------------


async def format_response(state: ConversationState) -> dict[str, Any]:
    """Formatea la respuesta final para WhatsApp (*negrita*, listas con -)."""
    from agents.prompts import FORMAT_INSTRUCTIONS

    raw = state.get("final_response", "")
    if not raw:
        return {"final_response": "Lo siento, no pude procesar tu consulta. ¿Puedes reformularla?"}

    llm = create_llm()
    response = await llm.ainvoke(
        [
            {"role": "system", "content": FORMAT_INSTRUCTIONS},
            {"role": "user", "content": raw},
        ]
    )
    formatted = response.content.strip()

    # Registrar la respuesta en el historial
    return {
        "final_response": formatted,
        "messages": [AIMessage(content=formatted)],
    }
