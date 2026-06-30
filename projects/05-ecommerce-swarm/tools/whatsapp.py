"""Cliente async de WhatsApp Cloud API (Meta Graph API) con httpx."""

import hashlib
import hmac
import logging
from typing import Any, Optional

import httpx

from config import get_settings

logger = logging.getLogger(__name__)

WHATSAPP_MAX_CHARS = 4000
GRAPH_API_VERSION = "v19.0"


class WhatsAppClient:
    """Cliente httpx reutilizable para la Graph API de WhatsApp."""

    def __init__(self) -> None:
        settings = get_settings()
        self.phone_id = settings.whatsapp_phone_id
        self.token = settings.whatsapp_token
        self.base_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{self.phone_id}/messages"
        self.headers = {"Authorization": f"Bearer {self.token}"}

    async def _post(self, body: dict) -> dict:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(self.base_url, headers=self.headers, json=body)
            resp.raise_for_status()
            return resp.json()


_client: WhatsAppClient | None = None


def get_whatsapp_client() -> WhatsAppClient:
    global _client
    if _client is None:
        _client = WhatsAppClient()
    return _client


def verify_webhook_signature(payload: bytes, signature_header: Optional[str]) -> bool:
    """Valida X-Hub-Signature-256 del webhook de Meta."""
    if not signature_header:
        return False

    settings = get_settings()
    expected = hmac.new(
        settings.whatsapp_app_secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    received = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, received)


def _split_message(text: str, max_len: int = WHATSAPP_MAX_CHARS) -> list[str]:
    """Divide mensajes largos en chunks respetando párrafos y palabras."""
    if len(text) <= max_len:
        return [text]

    chunks: list[str] = []
    current = ""
    for paragraph in text.split("\n"):
        if len(current) + len(paragraph) + 1 <= max_len:
            current = f"{current}\n{paragraph}".strip()
        else:
            if current:
                chunks.append(current)
            if len(paragraph) <= max_len:
                current = paragraph
            else:
                words = paragraph.split(" ")
                current = ""
                for word in words:
                    if len(current) + len(word) + 1 <= max_len:
                        current = f"{current} {word}".strip()
                    else:
                        if current:
                            chunks.append(current)
                        current = word
    if current:
        chunks.append(current)
    return chunks


def _normalize_phone(phone: str) -> str:
    return phone.lstrip("+")


async def send_message(phone: str, text: str) -> list[str]:
    """
    Envía mensaje de texto por WhatsApp.
    Auto-divide si supera 4000 caracteres.
    """
    client = get_whatsapp_client()
    sent_ids: list[str] = []

    for chunk in _split_message(text):
        data = await client._post(
            {
                "messaging_product": "whatsapp",
                "to": _normalize_phone(phone),
                "type": "text",
                "text": {"body": chunk},
            }
        )
        msg_id = data.get("messages", [{}])[0].get("id")
        if msg_id:
            sent_ids.append(msg_id)

    return sent_ids


async def mark_as_read(message_id: str) -> None:
    """Marca mensaje como leído (ticks azules al usuario)."""
    client = get_whatsapp_client()
    await client._post(
        {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }
    )


async def send_template(
    phone: str,
    template_name: str,
    params: list[str] | None = None,
    language_code: str = "es",
) -> str | None:
    """
    Envía mensaje de plantilla aprobada (útil para escaladas proactivas).
    params: valores para variables {{1}}, {{2}}, etc. del body de la plantilla.
    """
    components: list[dict[str, Any]] = []
    if params:
        components.append(
            {
                "type": "body",
                "parameters": [{"type": "text", "text": p} for p in params],
            }
        )

    body: dict[str, Any] = {
        "messaging_product": "whatsapp",
        "to": _normalize_phone(phone),
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code},
        },
    }
    if components:
        body["template"]["components"] = components

    client = get_whatsapp_client()
    data = await client._post(body)
    return data.get("messages", [{}])[0].get("id")


async def notify_escalation(phone: str, message: str, intent: str) -> None:
    """
    Notifica escalada: intenta plantilla WhatsApp, luego webhook opcional.
    Plantilla por defecto: 'escalacion_soporte' (debe existir en Meta Business).
    """
    settings = get_settings()
    template_name = settings.whatsapp_escalation_template

    try:
        await send_template(
            phone,
            template_name,
            params=[phone, intent[:50], message[:100]],
        )
        logger.info("Escalada enviada vía plantilla %s a %s", template_name, phone)
    except httpx.HTTPError:
        logger.warning(
            "Plantilla %s no disponible; escalada registrada en logs para %s",
            template_name,
            phone,
        )

    if not settings.escalation_webhook_url:
        return

    payload = {
        "phone": phone,
        "intent": intent,
        "message": message,
        "type": "escalation",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(settings.escalation_webhook_url, json=payload)
