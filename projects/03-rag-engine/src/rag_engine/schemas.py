"""Typed outputs for the RAG pipeline."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SourceCitation(BaseModel):
    """One retrieved chunk that supported the answer."""

    source: str = Field(description="Origin of the chunk, e.g. the filename.")
    score: float = Field(description="Similarity score from the vector search.")
    snippet: str = Field(description="Short excerpt of the supporting text.")


class GroundedAnswer(BaseModel):
    """The LLM's structured reply, constrained to be grounded in context."""

    answer: str = Field(description="The answer, or an explicit 'not enough information'.")
    answered: bool = Field(
        description="True if the context actually contained the answer.",
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Model's confidence the answer is correct and grounded.",
    )


class RAGAnswer(BaseModel):
    """Full pipeline result: the grounded answer plus its retrieval evidence."""

    question: str
    answer: str
    answered: bool
    confidence: float
    sources: list[SourceCitation]
