"""A thin, dependency-light wrapper around Qdrant.

We deliberately don't hide Qdrant behind a heavy abstraction: the goal is to show clean,
readable use of a real vector database (collection lifecycle, payload storage, similarity
search) rather than to build a framework.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Iterable, Sequence

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from .config import Settings, get_settings
from .providers import get_embeddings


@dataclass(slots=True)
class RetrievedChunk:
    """A single search hit: the stored text, its metadata and the similarity score."""

    text: str
    score: float
    metadata: dict


class VectorStore:
    """Create collections, upsert embedded documents and run similarity search."""

    def __init__(self, *, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client = QdrantClient(
            url=self._settings.qdrant_url,
            api_key=self._settings.qdrant_api_key or None,
        )
        self._embeddings = get_embeddings(settings=self._settings)
        self._collection = self._settings.qdrant_collection

    # ---- collection lifecycle ----------------------------------------------
    def ensure_collection(self, *, recreate: bool = False) -> None:
        """Create the collection if needed, inferring vector size from the embeddings."""
        exists = self._client.collection_exists(self._collection)
        if exists and not recreate:
            return
        if exists and recreate:
            self._client.delete_collection(self._collection)

        probe = self._embeddings.embed_query("dimension probe")
        self._client.create_collection(
            collection_name=self._collection,
            vectors_config=VectorParams(size=len(probe), distance=Distance.COSINE),
        )

    # ---- writes -------------------------------------------------------------
    def add_texts(
        self,
        texts: Sequence[str],
        metadatas: Sequence[dict] | None = None,
        *,
        batch_size: int = 64,
    ) -> int:
        """Embed and upsert ``texts`` (with optional per-text metadata). Returns count."""
        metadatas = list(metadatas or [{} for _ in texts])
        if len(metadatas) != len(texts):
            raise ValueError("texts and metadatas must be the same length")

        total = 0
        for start in range(0, len(texts), batch_size):
            chunk_texts = list(texts[start : start + batch_size])
            chunk_meta = metadatas[start : start + batch_size]
            vectors = self._embeddings.embed_documents(chunk_texts)
            points = [
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload={"text": text, **meta},
                )
                for text, vector, meta in zip(chunk_texts, vectors, chunk_meta)
            ]
            self._client.upsert(collection_name=self._collection, points=points)
            total += len(points)
        return total

    # ---- reads --------------------------------------------------------------
    def search(
        self,
        query: str,
        *,
        top_k: int = 4,
        where: dict | None = None,
    ) -> list[RetrievedChunk]:
        """Return the ``top_k`` most similar chunks, optionally filtered by payload."""
        vector = self._embeddings.embed_query(query)
        query_filter = _build_filter(where)
        hits = self._client.search(
            collection_name=self._collection,
            query_vector=vector,
            limit=top_k,
            query_filter=query_filter,
            with_payload=True,
        )
        results: list[RetrievedChunk] = []
        for hit in hits:
            payload = dict(hit.payload or {})
            text = payload.pop("text", "")
            results.append(RetrievedChunk(text=text, score=hit.score, metadata=payload))
        return results

    def count(self) -> int:
        return self._client.count(self._collection, exact=True).count


def _build_filter(where: dict | None) -> Filter | None:
    if not where:
        return None
    conditions: Iterable[FieldCondition] = (
        FieldCondition(key=key, match=MatchValue(value=value))
        for key, value in where.items()
    )
    return Filter(must=list(conditions))
