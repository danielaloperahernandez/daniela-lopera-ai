"""ai_core - a small, provider-agnostic foundation for the portfolio projects.

Public surface:
    get_settings()    -> cached Settings loaded from the environment
    get_chat_model()  -> a LangChain chat model for the configured provider
    get_embeddings()  -> a LangChain embeddings model for the configured provider
    structured_chat() -> one-shot call that returns a validated Pydantic object
    VectorStore       -> thin Qdrant wrapper (create / upsert / search)
    load_prompt()     -> load a versioned prompt template from prompts/*.yaml
"""

from .config import Settings, get_settings
from .providers import get_chat_model, get_embeddings, structured_chat
from .prompts import Prompt, load_prompt
from .vectorstore import RetrievedChunk, VectorStore

__all__ = [
    "Settings",
    "get_settings",
    "get_chat_model",
    "get_embeddings",
    "structured_chat",
    "Prompt",
    "load_prompt",
    "VectorStore",
    "RetrievedChunk",
]

__version__ = "0.1.0"
