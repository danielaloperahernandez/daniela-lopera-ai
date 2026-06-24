"""The pipeline should retrieve, ground its answer, and abstain when there is no context."""

from __future__ import annotations

import rag_engine.pipeline as pipeline_mod
from ai_core import RetrievedChunk
from rag_engine import RAGPipeline
from rag_engine.schemas import GroundedAnswer

from conftest import FakeVectorStore


def test_abstains_when_no_context() -> None:
    store = FakeVectorStore(hits=[])
    pipeline = RAGPipeline(store=store)

    result = pipeline.ask("anything?")

    assert result.answered is False
    assert result.confidence == 0.0
    assert result.sources == []
    assert "enough information" in result.answer.lower()


def test_answers_from_context(monkeypatch) -> None:
    hits = [
        RetrievedChunk(
            text="Qdrant collections use Cosine distance.",
            score=0.91,
            metadata={"source": "qdrant.md", "chunk": 1},
        )
    ]
    store = FakeVectorStore(hits=hits)

    def fake_structured_chat(schema, system, user, **kwargs):
        assert "Cosine" in user  # retrieved context made it into the prompt
        return GroundedAnswer(answer="Cosine distance.", answered=True, confidence=0.95)

    monkeypatch.setattr(pipeline_mod, "structured_chat", fake_structured_chat)

    pipeline = RAGPipeline(store=store)
    result = pipeline.ask("What distance metric is used?")

    assert result.answered is True
    assert result.answer == "Cosine distance."
    assert result.sources[0].source == "qdrant.md"
    assert result.sources[0].score == 0.91
