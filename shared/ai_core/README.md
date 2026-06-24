# ai_core - shared AI foundation

A small, readable foundation shared by all three projects. It does three things well:

1. **Provider-agnostic models** - one env var (`LLM_PROVIDER`) switches between
   OpenAI, Anthropic and Gemini. Callers never import an SDK.
2. **Qdrant vector store** - a thin wrapper for collection lifecycle, upsert and search.
3. **Versioned prompts** - YAML templates with semantic versions (see [`prompts/`](prompts)).

## Why it exists

Every project needs "talk to an LLM" and "search a vector DB". Centralizing that keeps the
projects focused on their actual problem and demonstrates clean, reusable engineering.

## API

```python
from ai_core import (
    get_settings,       # cached, validated env config
    get_chat_model,     # LangChain chat model for the configured provider
    get_embeddings,     # LangChain embeddings for the configured provider
    structured_chat,    # one-shot call -> validated Pydantic object (with retries)
    VectorStore,        # Qdrant wrapper
    load_prompt,        # load a versioned prompt template
)
```

### Example: structured output with automatic retries

```python
from pydantic import BaseModel
from ai_core import structured_chat, load_prompt

class Intent(BaseModel):
    category: str
    priority: str
    escalate: bool
    language: str

prompt = load_prompt("intent_classifier")
system, user = prompt.render(message="My invoice is wrong and I'm furious")
result = structured_chat(Intent, system, user)   # -> Intent(...)
```

### Example: vector search

```python
from ai_core import VectorStore

store = VectorStore()
store.ensure_collection()
store.add_texts(["Qdrant is a vector database."], [{"source": "docs"}])
hits = store.search("what is qdrant?", top_k=3)
```

## Install

```bash
pip install -r requirements.txt
```

## Configuration

All configuration is environment-driven; see the repo-root [`.env.example`](../../.env.example).
Switch providers with `LLM_PROVIDER=openai|anthropic|gemini`. Note that Anthropic has no
embeddings API, so embeddings fall back to OpenAI automatically.
