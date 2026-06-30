"""
FastAPI: webhook WhatsApp (GET verificación, POST mensajes),
orquestación del grafo LangGraph y envío de respuestas.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request, Response

from config import get_settings
from graph.builder import get_compiled_graph
from memory.session import (
    append_user_message,
    check_rate_limit,
    close_redis,
    is_duplicate_message,
    load_session,
    save_session,
)
from models.schemas import WebhookPayload
from tools.whatsapp import mark_as_read, send_message, verify_webhook_signature

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: compila el grafo. Shutdown: cierra conexión Redis."""
    get_compiled_graph()
    logger.info("Grafo LangGraph compilado y listo")
    yield
    await close_redis()
    logger.info("Recursos liberados")


app = FastAPI(
    title="Ecommerce Swarm",
    description="Atención al cliente e-commerce vía WhatsApp con LangGraph + Gemini",
    lifespan=lifespan,
)


@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
):
    """Verificación del webhook de Meta (WhatsApp Cloud API)."""
    settings = get_settings()
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        logger.info("Webhook verificado correctamente")
        return Response(content=hub_challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Token de verificación inválido")


@app.post("/webhook")
async def receive_webhook(request: Request):
    """
    Recibe mensajes entrantes de WhatsApp.
    Valida firma, idempotencia, rate limit y ejecuta el grafo.
    """
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")

    if not verify_webhook_signature(body, signature):
        raise HTTPException(status_code=401, detail="Firma inválida")

    payload = WebhookPayload.model_validate_json(body)

    for entry in payload.entry:
        for change in entry.changes:
            value = change.value
            if not value.messages:
                continue

            for msg in value.messages:
                if msg.type != "text" or not msg.text:
                    continue

                phone = msg.from_
                text = msg.text.body
                message_id = msg.id

                # Idempotencia: ignorar duplicados en ventana de 60s
                if await is_duplicate_message(message_id):
                    logger.info("Mensaje duplicado ignorado: %s", message_id)
                    continue

                # Rate limit por número
                if not await check_rate_limit(phone):
                    await send_message(
                        phone,
                        "Has enviado muchos mensajes. Espera un momento e intenta de nuevo.",
                    )
                    continue

                await mark_as_read(message_id)

                # Cargar sesión, añadir mensaje y ejecutar grafo
                state = await load_session(phone)
                state = append_user_message(state, text)
                state["message_id"] = message_id
                state["phone"] = phone

                graph = get_compiled_graph()
                result = await graph.ainvoke(state)

                await save_session(result)

                response_text = result.get("final_response", "")
                if response_text:
                    await send_message(phone, response_text)

    return {"status": "ok"}


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "ecommerce-swarm"}
