"""Optional thin HTTP layer over the RAG pipeline.

The pipeline is pure Python, but exposing a tiny endpoint lets other systems (like the n8n
agent in Project 2) query the knowledge base over HTTP. Run with:

    pip install "fastapi>=0.111" "uvicorn[standard]>=0.30"
    uvicorn rag_engine.serve:app --port 8001
"""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from .pipeline import RAGPipeline
from .schemas import RAGAnswer

app = FastAPI(title="RAG Engine API", version="0.1.0")
_pipeline: RAGPipeline | None = None


def _get_pipeline() -> RAGPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = RAGPipeline()
    return _pipeline


class AskRequest(BaseModel):
    question: str
    top_k: int = 4


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/ask", response_model=RAGAnswer)
def ask(req: AskRequest) -> RAGAnswer:
    pipeline = RAGPipeline(top_k=req.top_k) if req.top_k != 4 else _get_pipeline()
    return pipeline.ask(req.question)
