"""
Configuración central del sistema ecommerce_swarm.
Usa pydantic-settings para cargar variables de entorno.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# ---------------------------------------------------------------------------
# SHOPIFY API — ¿Cuál usar?
# ---------------------------------------------------------------------------
#
# Admin API REST
#   - Requiere token de acceso privado (Custom App en Shopify Admin).
#   - Permite lectura Y escritura: pedidos, reembolsos, clientes, productos.
#   - Ideal para bots de atención al cliente porque necesitamos leer datos
#     sensibles de pedidos y procesar devoluciones.
#   - Endpoint base: https://{store}.myshopify.com/admin/api/2024-01/
#
# Storefront API
#   - Token público o privado de storefront; acceso de solo lectura.
#   - Expone catálogo, precios y checkout — NO puede ver pedidos ni clientes.
#   - Útil para vitrinas headless, no para soporte post-venta.
#
# DECISIÓN: Admin API REST con acceso privado.
# Scopes necesarios en la Custom App:
#   - read_products, read_orders, read_customers, write_orders (reembolsos)
#
# Cómo obtener el token: ver README.md → "Configurar Shopify Admin API"
# ---------------------------------------------------------------------------


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    gemini_api_key: str
    gemini_model: str = "gemini-1.5-pro"

    # Shopify Admin API REST
    shopify_store_url: str  # ej: mi-tienda.myshopify.com
    shopify_access_token: str
    shopify_api_version: str = "2024-01"

    # WhatsApp Cloud API (Meta)
    whatsapp_token: str
    whatsapp_phone_id: str
    whatsapp_verify_token: str
    whatsapp_app_secret: str  # para validar X-Hub-Signature-256

    # Redis (sesiones, rate limit, idempotencia)
    redis_url: str = "redis://localhost:6379/0"

    # ChromaDB
    chroma_path: str = "./data/chroma_db"
    chroma_collection: str = "ecommerce_kb"

    # Seguridad / límites
    rate_limit_messages_per_minute: int = 10
    idempotency_ttl_seconds: int = 60
    session_ttl_seconds: int = 86400  # 24 h
    rag_score_threshold: float = 0.75

    # Escalada opcional
    escalation_webhook_url: str = ""  # Slack/Discord/n8n
    whatsapp_escalation_template: str = "escalacion_soporte"

    @property
    def shopify_base_url(self) -> str:
        store = self.shopify_store_url.rstrip("/")
        if not store.startswith("http"):
            store = f"https://{store}"
        return f"{store}/admin/api/{self.shopify_api_version}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
