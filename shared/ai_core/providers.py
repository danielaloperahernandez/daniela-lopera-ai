"""Provider-agnostic LLM and embeddings factories.

The rest of the codebase never imports an SDK directly. It asks for ``get_chat_model()``
or ``get_embeddings()`` and gets back a LangChain object wired to whatever provider the
environment selected. Swapping OpenAI -> Anthropic -> Gemini is a one-line ``.env`` change.

``structured_chat()`` is the workhorse for "give me JSON that matches this schema", with
retry/backoff so transient rate limits don't break a flow.
"""

from __future__ import annotations

from typing import TypeVar

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.embeddings import Embeddings
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import Provider, Settings, get_settings

TModel = TypeVar("TModel", bound=BaseModel)


# --------------------------------------------------------------------------- #
# Chat models
# --------------------------------------------------------------------------- #
def get_chat_model(
    *,
    provider: Provider | None = None,
    temperature: float | None = None,
    settings: Settings | None = None,
) -> BaseChatModel:
    """Build a LangChain chat model for the configured (or overridden) provider."""
    settings = settings or get_settings()
    provider = provider or settings.llm_provider
    temperature = settings.llm_temperature if temperature is None else temperature

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.openai_chat_model,
            temperature=temperature,
            api_key=settings.require_key("openai"),
            timeout=settings.llm_request_timeout,
            max_retries=0,  # we handle retries ourselves in structured_chat
        )

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=settings.anthropic_chat_model,
            temperature=temperature,
            api_key=settings.require_key("anthropic"),
            timeout=settings.llm_request_timeout,
            max_retries=0,
        )

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.gemini_chat_model,
            temperature=temperature,
            google_api_key=settings.require_key("gemini"),
            timeout=settings.llm_request_timeout,
            max_retries=0,
        )

    raise ValueError(f"Unknown provider: {provider!r}")


# --------------------------------------------------------------------------- #
# Embeddings
# --------------------------------------------------------------------------- #
def get_embeddings(*, settings: Settings | None = None) -> Embeddings:
    """Build a LangChain embeddings model for the configured embeddings provider."""
    settings = settings or get_settings()
    provider = settings.embeddings_provider

    if provider in ("openai", "anthropic"):
        # Anthropic has no embeddings API, so we use OpenAI embeddings there too.
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(
            model=settings.openai_embeddings_model,
            api_key=settings.require_key("openai"),
        )

    if provider == "gemini":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        return GoogleGenerativeAIEmbeddings(
            model=f"models/{settings.gemini_embeddings_model}",
            google_api_key=settings.require_key("gemini"),
        )

    raise ValueError(f"Unknown embeddings provider: {provider!r}")


# --------------------------------------------------------------------------- #
# Structured generation with retries
# --------------------------------------------------------------------------- #
class _Retryable(Exception):
    """Wraps transient provider errors so tenacity retries only the right ones."""


def _is_transient(exc: BaseException) -> bool:
    name = exc.__class__.__name__.lower()
    text = str(exc).lower()
    transient_markers = ("ratelimit", "timeout", "overloaded", "503", "429", "connection")
    return any(m in name or m in text for m in transient_markers)


def structured_chat(
    schema: type[TModel],
    system_prompt: str,
    user_prompt: str,
    *,
    provider: Provider | None = None,
    temperature: float | None = None,
    settings: Settings | None = None,
) -> TModel:
    """Call the LLM and parse the reply into ``schema`` (a Pydantic model).

    Uses LangChain's ``with_structured_output`` so the provider returns JSON that already
    matches the schema, and wraps the call in exponential-backoff retries for rate limits.
    """
    settings = settings or get_settings()
    model = get_chat_model(provider=provider, temperature=temperature, settings=settings)
    structured = model.with_structured_output(schema)
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]

    @retry(
        reraise=True,
        stop=stop_after_attempt(settings.llm_max_retries + 1),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        retry=retry_if_exception_type(_Retryable),
    )
    def _invoke() -> TModel:
        try:
            return structured.invoke(messages)  # type: ignore[return-value]
        except Exception as exc:  # noqa: BLE001 - we re-classify below
            if _is_transient(exc):
                raise _Retryable(str(exc)) from exc
            raise

    return _invoke()
