"""rag_engine - a small, evaluable Retrieval-Augmented Generation pipeline.

Public surface:
    ingest_paths()    -> chunk + embed + store documents in Qdrant
    RAGPipeline       -> retrieve + answer with grounded, structured output
    RAGAnswer         -> the structured result type
"""

from .ingest import ingest_paths
from .pipeline import RAGPipeline
from .schemas import RAGAnswer

__all__ = ["ingest_paths", "RAGPipeline", "RAGAnswer"]
