"""Redis async: serialización de ConversationState con TTL de 24h."""

import json
import logging
import time
from typing import Optional

import redis.asyncio as aioredis
from langchain_core.messages import HumanMessage, messages_from_dict, messages_to_dict

from config import get_settings
from graph.state import ConversationState

logger = logging.getLogger(__name__)

_redis: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.close()
        _redis = None


def _session_key(phone: str) -> str:
    return f"session:{phone}"


def _idempotency_key(message_id: str) -> str:
    return f"idempotency:{message_id}"


def _rate_limit_key(phone: str) -> str:
    return f"ratelimit:{phone}"


def _state_to_dict(state: ConversationState) -> dict:
    """Serializa ConversationState a dict JSON-compatible."""
    return {
        "phone": state.get("phone", ""),
        "intent": state.get("intent", ""),
        "shopify_customer_id": state.get("shopify_customer_id", ""),
        "attempts": state.get("attempts", 0),
        "requires_human": state.get("requires_human", False),
        "final_response": state.get("final_response", ""),
        "message_id": state.get("message_id", ""),
        "needs_refund": state.get("needs_refund", False),
        # BaseMessage requiere messages_to_dict para serialización correcta
        "messages": messages_to_dict(state.get("messages", [])),
    }


def _dict_to_state(data: dict, phone: str) -> ConversationState:
    """Deserializa dict JSON a ConversationState."""
    messages = messages_from_dict(data.get("messages", []))
    return ConversationState(
        messages=messages,
        phone=data.get("phone", phone),
        intent=data.get("intent", ""),
        shopify_customer_id=data.get("shopify_customer_id", ""),
        attempts=data.get("attempts", 0),
        requires_human=data.get("requires_human", False),
        final_response=data.get("final_response", ""),
        message_id=data.get("message_id", ""),
        needs_refund=data.get("needs_refund", False),
    )


def _empty_state(phone: str) -> ConversationState:
    return ConversationState(
        messages=[],
        phone=phone,
        intent="",
        shopify_customer_id="",
        attempts=0,
        requires_human=False,
        final_response="",
        message_id="",
        needs_refund=False,
    )


async def load_state(phone: str) -> ConversationState | None:
    """Carga ConversationState desde Redis. Retorna None si no existe sesión."""
    r = await get_redis()
    raw = await r.get(_session_key(phone))
    if not raw:
        return None
    try:
        return _dict_to_state(json.loads(raw), phone)
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning("Sesión corrupta para %s: %s", phone, exc)
        return None


async def save_state(phone: str, state: ConversationState) -> None:
    """Persiste ConversationState en Redis con TTL de 24h."""
    settings = get_settings()
    r = await get_redis()
    state["phone"] = phone
    payload = json.dumps(_state_to_dict(state), ensure_ascii=False)
    await r.setex(_session_key(phone), settings.session_ttl_seconds, payload)


async def load_session(phone: str) -> ConversationState:
    """Compatibilidad con main.py: retorna sesión existente o estado vacío."""
    state = await load_state(phone)
    return state if state is not None else _empty_state(phone)


async def save_session(state: ConversationState) -> None:
    """Compatibilidad con main.py: guarda usando el phone del estado."""
    phone = state.get("phone", "")
    if phone:
        await save_state(phone, state)


async def is_duplicate_message(message_id: str) -> bool:
    """Retorna True si el message_id ya fue procesado (ventana configurable)."""
    if not message_id:
        return False
    settings = get_settings()
    r = await get_redis()
    key = _idempotency_key(message_id)
    if await r.exists(key):
        return True
    await r.setex(key, settings.idempotency_ttl_seconds, "1")
    return False


async def check_rate_limit(phone: str) -> bool:
    """Sliding window: máximo N mensajes por minuto por número."""
    settings = get_settings()
    r = await get_redis()
    key = _rate_limit_key(phone)
    now = time.time()
    window_start = now - 60

    pipe = r.pipeline()
    pipe.zremrangebyscore(key, 0, window_start)
    pipe.zadd(key, {str(now): now})
    pipe.zcard(key)
    pipe.expire(key, 60)
    _, _, count, _ = await pipe.execute()

    return count <= settings.rate_limit_messages_per_minute


def append_user_message(state: ConversationState, text: str) -> ConversationState:
    """Añade un HumanMessage al historial en memoria."""
    state["messages"] = list(state.get("messages", [])) + [HumanMessage(content=text)]
    return state
