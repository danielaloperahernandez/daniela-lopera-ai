"""Make the package importable and provide lightweight fakes for offline tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_core import RetrievedChunk  # noqa: E402


class FakeVectorStore:
    """In-memory stand-in for the Qdrant-backed VectorStore (no network needed)."""

    def __init__(self, hits: list[RetrievedChunk] | None = None) -> None:
        self.texts: list[str] = []
        self.metadatas: list[dict] = []
        self._hits = hits if hits is not None else []
        self.ensured = False

    def ensure_collection(self, *, recreate: bool = False) -> None:
        self.ensured = True

    def add_texts(self, texts, metadatas=None, *, batch_size: int = 64) -> int:
        self.texts.extend(texts)
        self.metadatas.extend(metadatas or [{} for _ in texts])
        return len(texts)

    def search(self, query: str, *, top_k: int = 4, where=None):
        return self._hits[:top_k]

    def count(self) -> int:
        return len(self.texts)


@pytest.fixture
def fake_store() -> FakeVectorStore:
    return FakeVectorStore()
