"""Centralized, environment-driven configuration.

Everything the projects need to know about providers, models and Qdrant lives here so
no module reads ``os.environ`` directly. Values come from the process environment (and a
local ``.env`` if present), which keeps secrets out of the codebase.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

Provider = Literal["openai", "anthropic", "gemini"]


class Settings(BaseSettings):
    """Strongly-typed settings, validated once at startup."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- provider selection -------------------------------------------------
    llm_provider: Provider = "openai"
    embeddings_provider: Provider = "openai"

    # ---- models per provider ------------------------------------------------
    openai_chat_model: str = "gpt-4o-mini"
    anthropic_chat_model: str = "claude-3-5-sonnet-latest"
    gemini_chat_model: str = "gemini-1.5-flash"

    openai_embeddings_model: str = "text-embedding-3-small"
    gemini_embeddings_model: str = "text-embedding-004"

    # ---- api keys -----------------------------------------------------------
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    gemini_api_key: str | None = None

    # ---- qdrant -------------------------------------------------------------
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "portfolio_knowledge"

    # ---- generation tuning --------------------------------------------------
    llm_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    llm_max_retries: int = Field(default=5, ge=0, le=10)
    llm_request_timeout: int = Field(default=60, ge=1)

    # ---- convenience accessors ---------------------------------------------
    @property
    def chat_model_name(self) -> str:
        return {
            "openai": self.openai_chat_model,
            "anthropic": self.anthropic_chat_model,
            "gemini": self.gemini_chat_model,
        }[self.llm_provider]

    @property
    def embeddings_model_name(self) -> str:
        return {
            "openai": self.openai_embeddings_model,
            "gemini": self.gemini_embeddings_model,
            # Anthropic has no first-party embeddings; fall back to OpenAI.
            "anthropic": self.openai_embeddings_model,
        }[self.embeddings_provider]

    def require_key(self, provider: Provider) -> str:
        """Return the API key for ``provider`` or raise a clear error."""
        key = {
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
            "gemini": self.gemini_api_key,
        }[provider]
        if not key:
            raise RuntimeError(
                f"Missing API key for provider '{provider}'. "
                f"Set {provider.upper()}_API_KEY in your environment or .env file."
            )
        return key


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""
    return Settings()
