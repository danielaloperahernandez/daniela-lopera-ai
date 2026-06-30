"""Genera o amplía eval/dataset.jsonl con casos de prueba.

Modos:
  python -m eval.dataset_builder --seed          # 30 casos curados (preserva auto_generated)
  python -m eval.dataset_builder --from-redis    # Gemini + logs Redis → nuevos casos
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

DATASET_PATH = Path(__file__).parent / "dataset.jsonl"

CASES = [
    # --- RAG (8) ---
    {"id": "tc_001", "description": "Envíos a Pasto", "conversation": [{"role": "user", "content": "¿Hacen envíos a Pasto?"}], "expected": {"node": "rag_node", "tools_called": ["search_knowledge_base"], "tool_params": {"query": "Pasto"}, "response_must_contain": ["Pasto", "envío"], "response_must_not_contain": ["no tengo información"], "judge_criteria": "Confirma envíos a Pasto con tiempos o costos"}, "category": "rag", "difficulty": "easy"},
    {"id": "tc_002", "description": "Plazo devoluciones", "conversation": [{"role": "user", "content": "¿Cuál es la política de devoluciones y cuántos días tengo?"}], "expected": {"node": "rag_node", "tools_called": ["search_knowledge_base"], "tool_params": {"query": "devoluc"}, "response_must_contain": ["30", "día"], "response_must_not_contain": [], "judge_criteria": "Indica plazo de devolución claramente"}, "category": "rag", "difficulty": "easy"},
    {"id": "tc_003", "description": "Garantía electrónicos", "conversation": [{"role": "user", "content": "¿Qué garantía tienen los productos electrónicos?"}], "expected": {"node": "rag_node", "tools_called": ["search_knowledge_base"], "tool_params": {"query": "garantía"}, "response_must_contain": ["garantía", "12"], "response_must_not_contain": [], "judge_criteria": "Explica garantía de electrónicos"}, "category": "rag", "difficulty": "easy"},
    {"id": "tc_004", "description": "Horario atención humana", "conversation": [{"role": "user", "content": "¿Cuál es el horario de atención de agentes humanos?"}], "expected": {"node": "rag_node", "tools_called": ["search_knowledge_base"], "tool_params": {"query": "horario"}, "response_must_contain": ["horario"], "response_must_not_contain": [], "judge_criteria": "Informa horario de agentes humanos"}, "category": "rag", "difficulty": "easy"},
    {"id": "tc_005", "description": "Medios de pago Colombia", "conversation": [{"role": "user", "content": "¿Aceptan PSE o Nequi?"}], "expected": {"node": "rag_node", "tools_called": ["search_knowledge_base"], "tool_params": {"query": "PSE"}, "response_must_contain": ["PSE", "Nequi"], "response_must_not_contain": [], "judge_criteria": "Lista medios de pago colombianos"}, "category": "rag", "difficulty": "medium"},
    {"id": "tc_006", "description": "Envío gratis umbral", "conversation": [{"role": "user", "content": "¿A partir de cuánto es el envío gratis?"}], "expected": {"node": "rag_node", "tools_called": ["search_knowledge_base"], "tool_params": {"query": "gratis"}, "response_must_contain": ["150", "gratis"], "response_must_not_contain": [], "judge_criteria": "Indica monto mínimo para envío gratis"}, "category": "rag", "difficulty": "medium"},
    {"id": "tc_007", "description": "Transportadoras", "conversation": [{"role": "user", "content": "¿Usan Servientrega o Coordinadora?"}], "expected": {"node": "rag_node", "tools_called": ["search_knowledge_base"], "tool_params": {"query": "Servientrega"}, "response_must_contain": ["Servientrega", "Coordinadora"], "response_must_not_contain": [], "judge_criteria": "Menciona transportadoras aliadas"}, "category": "rag", "difficulty": "medium"},
    {"id": "tc_008", "description": "Ambiguo envío+garantía", "conversation": [{"role": "user", "content": "Si compro un televisor, ¿cuánto tarda el envío y qué garantía tiene?"}], "expected": {"node": "rag_node", "tools_called": ["search_knowledge_base"], "tool_params": {"query": "envío"}, "response_must_contain": ["envío", "garantía"], "response_must_not_contain": [], "judge_criteria": "Responde envío y garantía en un solo mensaje"}, "category": "rag", "difficulty": "hard"},
    # --- Ventas (7) ---
    {"id": "tc_009", "description": "Buscar Sony", "conversation": [{"role": "user", "content": "Quiero ver audífonos Sony"}], "expected": {"node": "sales_node", "tools_called": ["search_products"], "tool_params": {"query": "Sony"}, "response_must_contain": ["Sony", "899"], "response_must_not_contain": [], "judge_criteria": "Muestra audífonos Sony con precio"}, "category": "ventas", "difficulty": "easy"},
    {"id": "tc_010", "description": "Precio máximo", "conversation": [{"role": "user", "content": "Audífonos de máximo 600000 pesos"}], "expected": {"node": "sales_node", "tools_called": ["search_products"], "tool_params": {"query": "audífonos"}, "response_must_contain": ["549", "Samsung"], "response_must_not_contain": ["999"], "judge_criteria": "Filtra productos bajo el precio máximo"}, "category": "ventas", "difficulty": "easy"},
    {"id": "tc_011", "description": "Categoría audio", "conversation": [{"role": "user", "content": "Productos de categoría Audio"}], "expected": {"node": "sales_node", "tools_called": ["search_products"], "tool_params": {"category": "Audio"}, "response_must_contain": ["Audio"], "response_must_not_contain": [], "judge_criteria": "Lista productos de categoría Audio"}, "category": "ventas", "difficulty": "medium"},
    {"id": "tc_012", "description": "Detalle producto ID", "conversation": [{"role": "user", "content": "Detalle del producto 7001"}], "expected": {"node": "sales_node", "tools_called": ["search_products"], "tool_params": {}, "response_must_contain": ["7001", "Sony"], "response_must_not_contain": [], "judge_criteria": "Muestra detalle del producto solicitado"}, "category": "ventas", "difficulty": "medium"},
    {"id": "tc_013", "description": "Comparar Sony vs Samsung", "conversation": [{"role": "user", "content": "Compara audífonos Sony y Samsung en precio y stock"}], "expected": {"node": "sales_node", "tools_called": ["search_products"], "tool_params": {"query": "Sony"}, "response_must_contain": ["Sony", "Samsung"], "response_must_not_contain": [], "judge_criteria": "Compara al menos dos productos"}, "category": "ventas", "difficulty": "hard"},
    {"id": "tc_014", "description": "Mensaje corto precio", "conversation": [{"role": "user", "content": "precio?"}], "expected": {"node": "sales_node", "tools_called": ["search_products"], "tool_params": {}, "response_must_contain": ["Precio", "COP"], "response_must_not_contain": [], "judge_criteria": "Interpreta mensaje corto y ofrece precios"}, "category": "ventas", "difficulty": "hard"},
    {"id": "tc_015", "description": "Inglés headphones", "conversation": [{"role": "user", "content": "Do you have Sony headphones?"}], "expected": {"node": "sales_node", "tools_called": ["search_products"], "tool_params": {"query": "Sony"}, "response_must_contain": ["Sony"], "response_must_not_contain": [], "judge_criteria": "Responde búsqueda de audífonos Sony aunque esté en inglés"}, "category": "ventas", "difficulty": "hard"},
    # --- Pedidos (6) ---
    {"id": "tc_016", "description": "Estado pedido #1042", "conversation": [{"role": "user", "content": "¿Cuánto vale el pedido #1042?"}], "expected": {"node": "orders_node", "tools_called": ["get_order_by_number"], "tool_params": {"order_number": "#1042"}, "response_must_contain": ["1042", "899"], "response_must_not_contain": ["no coincide"], "judge_criteria": "Muestra total y estado del pedido #1042"}, "category": "pedidos", "difficulty": "easy"},
    {"id": "tc_017", "description": "Historial pedidos", "conversation": [{"role": "user", "content": "Muéstrame mis últimos pedidos"}], "expected": {"node": "orders_node", "tools_called": ["get_customer_orders"], "tool_params": {"phone": "+573001234567"}, "response_must_contain": ["1042", "1038"], "response_must_not_contain": [], "judge_criteria": "Lista pedidos recientes del cliente"}, "category": "pedidos", "difficulty": "easy"},
    {"id": "tc_018", "description": "Tracking guía", "conversation": [{"role": "user", "content": "¿Cuál es el tracking del pedido #1042?"}], "expected": {"node": "orders_node", "tools_called": ["get_order_by_number"], "tool_params": {"order_number": "#1042"}, "response_must_contain": ["Servientrega", "7348"], "response_must_not_contain": [], "judge_criteria": "Proporciona número de rastreo"}, "category": "pedidos", "difficulty": "medium"},
    {"id": "tc_019", "description": "Pedido sin despachar", "conversation": [{"role": "user", "content": "Estado del pedido #1038"}], "expected": {"node": "orders_node", "tools_called": ["get_order_by_number"], "tool_params": {"order_number": "#1038"}, "response_must_contain": ["1038", "preparación"], "response_must_not_contain": [], "judge_criteria": "Indica que pedido #1038 está en preparación"}, "category": "pedidos", "difficulty": "medium"},
    {"id": "tc_020", "description": "Cuándo llega (corto)", "conversation": [{"role": "user", "content": "¿cuándo llega mi pedido #1042?"}], "expected": {"node": "orders_node", "tools_called": ["get_order_by_number"], "tool_params": {"order_number": "#1042"}, "response_must_contain": ["1042"], "response_must_not_contain": [], "judge_criteria": "Responde sobre llegada/estado del pedido"}, "category": "pedidos", "difficulty": "hard"},
    {"id": "tc_021", "description": "Pedido + devolución mezclado", "conversation": [{"role": "user", "content": "Quiero saber el estado del #1042 y si puedo devolverlo"}], "expected": {"node": ["orders_node", "refunds_node"], "tools_called": ["get_order_by_number"], "tool_params": {"order_number": "#1042"}, "response_must_contain": ["1042"], "response_must_not_contain": [], "judge_criteria": "Atiende consulta mixta de pedido y devolución"}, "category": "pedidos", "difficulty": "hard"},
    # --- Clientes (4) ---
    {"id": "tc_022", "description": "Buscar por teléfono", "conversation": [{"role": "user", "content": "Busca mi cuenta con este teléfono"}], "expected": {"node": "customers_node", "tools_called": ["get_customer_by_phone"], "tool_params": {"phone": "+573001234567"}, "response_must_contain": ["Juan", "5001"], "response_must_not_contain": [], "judge_criteria": "Identifica cliente por teléfono"}, "category": "clientes", "difficulty": "easy", "phone": "+573001234567"},
    {"id": "tc_023", "description": "Email registrado", "conversation": [{"role": "user", "content": "¿Cuál es el email de mi cuenta?"}], "expected": {"node": "customers_node", "tools_called": ["get_customer_by_phone"], "tool_params": {}, "response_must_contain": ["email", "juan"], "response_must_not_contain": [], "judge_criteria": "Muestra email del cliente autenticado"}, "category": "clientes", "difficulty": "medium"},
    {"id": "tc_024", "description": "Datos de cuenta", "conversation": [{"role": "user", "content": "Quiero ver los datos de mi perfil de cliente"}], "expected": {"node": "customers_node", "tools_called": ["get_customer_by_phone"], "tool_params": {}, "response_must_contain": ["Cliente", "Pérez"], "response_must_not_contain": [], "judge_criteria": "Muestra datos básicos del perfil"}, "category": "clientes", "difficulty": "medium"},
    {"id": "tc_025", "description": "Seguridad otro teléfono", "conversation": [{"role": "user", "content": "Busca la cuenta registrada con el teléfono +573009999999"}], "expected": {"node": "customers_node", "tools_called": ["get_customer_by_phone"], "tool_params": {"phone": "+573009999999"}, "response_must_contain": ["No encontré"], "response_must_not_contain": ["Juan", "1042"], "judge_criteria": "No expone datos de otro cliente"}, "category": "clientes", "difficulty": "hard", "phone": "+573009999999"},
    # --- Reembolsos (3) ---
    {"id": "tc_026", "description": "Solicitud devolución", "conversation": [{"role": "user", "content": "Quiero devolver el pedido #1042"}], "expected": {"node": "refunds_node", "tools_called": ["create_refund"], "tool_params": {"order_id": "9001"}, "response_must_contain": ["Reembolso", "1042"], "response_must_not_contain": [], "judge_criteria": "Inicia proceso de devolución/reembolso"}, "category": "reembolsos", "difficulty": "medium"},
    {"id": "tc_027", "description": "Producto roto", "conversation": [{"role": "user", "content": "Me llegó roto el pedido #1042, quiero reembolso"}], "expected": {"node": "refunds_node", "tools_called": ["create_refund"], "tool_params": {}, "response_must_contain": ["Reembolso"], "response_must_not_contain": [], "judge_criteria": "Empatía y proceso de reembolso por producto dañado"}, "category": "reembolsos", "difficulty": "medium"},
    {"id": "tc_028", "description": "Reembolso ya procesado", "conversation": [{"role": "user", "content": "Quiero otro reembolso del pedido #1042 que ya devolví"}], "expected": {"node": "refunds_node", "tools_called": ["create_refund", "get_order_by_number"], "tool_params": {}, "response_must_contain": ["Reembolso"], "response_must_not_contain": [], "judge_criteria": "Maneja solicitud duplicada de reembolso"}, "category": "reembolsos", "difficulty": "hard"},
    # --- Escalada (2) ---
    {"id": "tc_029", "description": "Escalada explícita", "conversation": [{"role": "user", "content": "Necesito hablar con una persona real"}], "expected": {"node": "escalation_node", "tools_called": [], "tool_params": {}, "response_must_contain": ["asesor", "24"], "response_must_not_contain": [], "judge_criteria": "Confirma escalada a humano con tiempos"}, "category": "escalada", "difficulty": "easy"},
    {"id": "tc_030", "description": "Frustración implícita", "conversation": [{"role": "user", "content": "Estoy harto, nadie me ayuda con esto"}], "expected": {"node": "escalation_node", "tools_called": [], "tool_params": {}, "response_must_contain": ["asesor"], "response_must_not_contain": [], "judge_criteria": "Detecta frustración y ofrece escalada"}, "category": "escalada", "difficulty": "hard"},
]

QUICK_IDS = ["tc_001", "tc_009", "tc_016", "tc_022", "tc_026", "tc_029", "tc_014", "tc_008", "tc_025", "tc_013"]

STATE_PATH = Path(__file__).parent / ".generation_state.json"
CONVERSATIONS_PER_BATCH = 50
CASES_PER_BATCH = 5


def _read_all_cases(path: Path | None = None) -> list[dict]:
    path = path or DATASET_PATH
    if not path.exists():
        return []
    cases = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def build_dataset(path: Path | None = None, preserve_auto: bool = True) -> int:
    """Escribe los 30 casos curados. Opcionalmente conserva auto_generated."""
    path = path or DATASET_PATH
    auto_cases = [c for c in _read_all_cases(path) if c.get("auto_generated")] if preserve_auto else []
    with path.open("w", encoding="utf-8") as f:
        for case in CASES:
            f.write(json.dumps(case, ensure_ascii=False) + "\n")
        for case in auto_cases:
            f.write(json.dumps(case, ensure_ascii=False) + "\n")
    return len(CASES) + len(auto_cases)


def ensure_dataset(path: Path | None = None) -> None:
    """Crea dataset.jsonl solo si no existe."""
    path = path or DATASET_PATH
    if not path.exists():
        build_dataset(path, preserve_auto=False)


def load_dataset(path: Path | None = None, category: str | None = None, quick: bool = False) -> list[dict]:
    path = path or DATASET_PATH
    ensure_dataset(path)
    cases = _read_all_cases(path)
    if quick:
        cases = [c for c in cases if c["id"] in QUICK_IDS]
    if category:
        cases = [c for c in cases if c.get("category") == category]
    return cases


def _load_generation_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {"indexed_count": 0, "last_run": None}


def _save_generation_state(state: dict) -> None:
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _next_auto_id(existing: list[dict]) -> str:
    nums = []
    for c in existing:
        m = re.match(r"tc_auto_(\d+)", c.get("id", ""))
        if m:
            nums.append(int(m.group(1)))
    n = max(nums, default=0) + 1
    return f"tc_auto_{n:03d}"


def append_auto_generated_cases(new_cases: list[dict], path: Path | None = None) -> int:
    """Append casos con auto_generated=true para revisión humana."""
    path = path or DATASET_PATH
    ensure_dataset(path)
    existing = _read_all_cases(path)
    existing_ids = {c["id"] for c in existing}

    appended = 0
    with path.open("a", encoding="utf-8") as f:
        for raw in new_cases:
            case = dict(raw)
            case["auto_generated"] = True
            case.setdefault("source", "redis_logs")
            if case.get("id") in existing_ids:
                case["id"] = _next_auto_id(existing)
            existing.append(case)
            existing_ids.add(case["id"])
            f.write(json.dumps(case, ensure_ascii=False) + "\n")
            appended += 1
    return appended


def _conversation_to_text(messages: list[dict]) -> str:
    lines = []
    for msg in messages:
        role = msg.get("type", msg.get("role", "unknown"))
        content = msg.get("data", {}).get("content", msg.get("content", ""))
        if isinstance(content, list):
            content = " ".join(str(x) for x in content)
        if role in ("human", "user"):
            lines.append(f"Usuario: {content}")
        elif role in ("ai", "assistant"):
            lines.append(f"Asistente: {content}")
    return "\n".join(lines)


async def fetch_conversations_from_redis(redis_url: str | None = None) -> list[dict]:
    """Lee sesiones reales session:* desde Redis."""
    import redis.asyncio as aioredis

    url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
    client = aioredis.from_url(url, decode_responses=True)
    conversations: list[dict] = []
    try:
        async for key in client.scan_iter("session:*"):
            raw = await client.get(key)
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            messages = data.get("messages", [])
            user_msgs = [
                m for m in messages
                if m.get("type", m.get("role")) in ("human", "user")
            ]
            if not user_msgs:
                continue
            phone = key.replace("session:", "", 1)
            conversations.append({
                "session_key": key,
                "phone": phone,
                "intent": data.get("intent", ""),
                "messages": messages,
                "text": _conversation_to_text(messages),
            })
    finally:
        await client.aclose()
    return conversations


def _build_generation_prompt(conversations: list[dict], count: int) -> str:
    samples = conversations[:20]
    blocks = []
    for i, conv in enumerate(samples, 1):
        blocks.append(f"--- Conversación {i} (intent={conv.get('intent', '?')}) ---\n{conv['text'][:800]}")

    return f"""Eres un ingeniero de QA para un bot de atención e-commerce por WhatsApp (Colombia).
A partir de conversaciones REALES de producción, genera {count} casos de prueba para evaluación automatizada.

Conversaciones de referencia:
{chr(10).join(blocks)}

Devuelve SOLO un JSON array válido (sin markdown) con exactamente {count} objetos con esta estructura:
{{
  "description": "resumen corto",
  "conversation": [{{"role": "user", "content": "mensaje del usuario"}}],
  "expected": {{
    "node": "rag_node|sales_node|orders_node|customers_node|refunds_node|escalation_node",
    "tools_called": ["nombre_tool"],
    "tool_params": {{}},
    "response_must_contain": ["palabra"],
    "response_must_not_contain": [],
    "judge_criteria": "criterio de evaluación"
  }},
  "category": "rag|ventas|pedidos|clientes|reembolsos|escalada",
  "difficulty": "easy|medium|hard"
}}

Reglas:
- Basate en patrones reales de las conversaciones (envíos, pedidos, productos, devoluciones).
- Un solo turno de usuario por caso (salvo que el log muestre multi-turn claro).
- tools_called válidos: search_knowledge_base, search_products, get_order_by_number,
  get_customer_orders, get_customer_by_phone, create_refund.
- No inventes IDs de pedido específicos salvo que aparezcan en los logs.
"""


def generate_cases_from_logs(conversations: list[dict], count: int, api_key: str | None = None) -> list[dict]:
    """Usa Gemini para sintetizar casos de prueba desde conversaciones reales."""
    if count <= 0:
        return []

    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY requerida para generar casos desde Redis")

    from langchain_google_genai import ChatGoogleGenerativeAI

    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=key, temperature=0.4)
    prompt = _build_generation_prompt(conversations, count)
    response = llm.invoke(prompt)
    text = response.content if hasattr(response, "content") else str(response)

    # Extraer JSON del response
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)

    cases = json.loads(text)
    if not isinstance(cases, list):
        raise ValueError("Gemini no devolvió un array JSON")

    existing = _read_all_cases()
    normalized = []
    for raw in cases[:count]:
        case = dict(raw)
        case["id"] = _next_auto_id(existing + normalized)
        case["auto_generated"] = True
        case["source"] = "redis_logs"
        normalized.append(case)
    return normalized


async def generate_from_redis(redis_url: str | None = None, api_key: str | None = None) -> int:
    """
    Por cada 50 conversaciones nuevas en Redis, genera 5 casos con Gemini
    y los appendea a dataset.jsonl para revisión humana.
    """
    conversations = await fetch_conversations_from_redis(redis_url)
    conversations.sort(key=lambda c: c["session_key"])

    state = _load_generation_state()
    indexed = int(state.get("indexed_count", 0))
    new_pool = conversations[indexed:]
    batches = len(new_pool) // CONVERSATIONS_PER_BATCH
    to_generate = batches * CASES_PER_BATCH

    if to_generate == 0:
        print(
            f"[i] {len(conversations)} conversaciones en Redis, "
            f"{len(new_pool)} nuevas desde último batch — "
            f"se necesitan {CONVERSATIONS_PER_BATCH - (len(new_pool) % CONVERSATIONS_PER_BATCH or CONVERSATIONS_PER_BATCH)} "
            f"más para el próximo lote de {CASES_PER_BATCH} casos."
        )
        return 0

    source_batch = new_pool[: batches * CONVERSATIONS_PER_BATCH]
    print(f"[*] Generando {to_generate} casos desde {len(source_batch)} conversaciones reales…")
    new_cases = generate_cases_from_logs(source_batch, to_generate, api_key=api_key)
    appended = append_auto_generated_cases(new_cases)

    state["indexed_count"] = indexed + len(source_batch)
    _save_generation_state(state)
    print(f"[OK] {appended} casos auto-generados añadidos a {DATASET_PATH} (auto_generated=true)")
    return appended


def main() -> int:
    parser = argparse.ArgumentParser(description="Dataset builder — casos curados y mejora continua")
    parser.add_argument("--seed", action="store_true", help="Regenerar 30 casos curados (conserva auto_generated)")
    parser.add_argument("--from-redis", action="store_true", help="Generar casos desde logs Redis vía Gemini")
    parser.add_argument("--redis-url", default=None, help="Override REDIS_URL")
    args = parser.parse_args()

    if args.from_redis:
        return asyncio.run(generate_from_redis(redis_url=args.redis_url)) or 0

    # Default / --seed: casos curados
    n = build_dataset(preserve_auto=True)
    print(f"Dataset listo: {n} casos en {DATASET_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
