"""The RAG pipeline: retrieve relevant context, then answer grounded in it."""

from __future__ import annotations

from ai_core import VectorStore, load_prompt, structured_chat

from .schemas import GroundedAnswer, RAGAnswer, SourceCitation


class RAGPipeline:
    """Retrieve-then-generate with grounded, structured output.

    The prompt forces the model to answer ONLY from retrieved context and to say so when
    the context is insufficient, which is what keeps faithfulness high in evaluation.
    """

    def __init__(self, *, top_k: int = 4, store: VectorStore | None = None) -> None:
        self._top_k = top_k
        self._store = store or VectorStore()
        self._prompt = load_prompt("rag_answer")

    def ask(self, question: str) -> RAGAnswer:
        chunks = self._store.search(question, top_k=self._top_k)

        if not chunks:
            return RAGAnswer(
                question=question,
                answer="I don't have enough information to answer that.",
                answered=False,
                confidence=0.0,
                sources=[],
            )

        context = "\n\n---\n\n".join(
            f"[{c.metadata.get('source', 'unknown')}] {c.text}" for c in chunks
        )
        system, user = self._prompt.render(context=context, question=question)
        grounded: GroundedAnswer = structured_chat(GroundedAnswer, system, user)

        sources = [
            SourceCitation(
                source=str(c.metadata.get("source", "unknown")),
                score=round(c.score, 4),
                snippet=c.text[:200].strip(),
            )
            for c in chunks
        ]

        return RAGAnswer(
            question=question,
            answer=grounded.answer,
            answered=grounded.answered,
            confidence=grounded.confidence,
            sources=sources,
        )
