"""ChromaDB RAG con embeddings de Google Generative AI."""

from pathlib import Path

import chromadb
from langchain_core.tools import tool
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from config import get_settings

DOCS_DIR = Path(__file__).parent.parent / "data" / "sample_docs"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

_embeddings: GoogleGenerativeAIEmbeddings | None = None


def _get_embeddings() -> GoogleGenerativeAIEmbeddings:
    global _embeddings
    if _embeddings is None:
        settings = get_settings()
        _embeddings = GoogleGenerativeAIEmbeddings(
            model="models/embedding-001",
            google_api_key=settings.gemini_api_key,
        )
    return _embeddings


def _get_chroma_client() -> chromadb.PersistentClient:
    settings = get_settings()
    return chromadb.PersistentClient(path=settings.chroma_path)


def _chunk_text(text: str, source: str) -> list[dict]:
    chunks: list[dict] = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunk = text[start:end].strip()
        if chunk:
            chunks.append({"content": chunk, "metadata": {"source": source}})
        if end >= len(text):
            break
        start = end - CHUNK_OVERLAP
    return chunks


def _get_collection(*, recreate: bool = False):
    settings = get_settings()
    client = _get_chroma_client()

    if recreate:
        try:
            client.delete_collection(settings.chroma_collection)
        except (ValueError, chromadb.errors.NotFoundError):
            pass

    return client.get_or_create_collection(name=settings.chroma_collection)


def ingest_docs() -> int:
    """
    Carga archivos .txt de data/sample_docs/ en ChromaDB.
    Divide en chunks de 500 caracteres con overlap de 50.
    """
    settings = get_settings()
    embeddings = _get_embeddings()
    collection = _get_collection(recreate=True)

    all_docs: list[str] = []
    all_meta: list[dict] = []
    all_ids: list[str] = []
    all_embeddings: list[list[float]] = []

    doc_id = 0
    for filepath in sorted(DOCS_DIR.glob("*.txt")):
        text = filepath.read_text(encoding="utf-8")
        for chunk in _chunk_text(text, filepath.name):
            vector = embeddings.embed_query(chunk["content"])
            all_docs.append(chunk["content"])
            all_meta.append(chunk["metadata"])
            all_ids.append(f"doc_{doc_id}")
            all_embeddings.append(vector)
            doc_id += 1

    if all_docs:
        collection.add(
            documents=all_docs,
            metadatas=all_meta,
            ids=all_ids,
            embeddings=all_embeddings,
        )

    return len(all_docs)


def _distance_to_score(distance: float) -> float:
    """Convierte distancia L2 de ChromaDB a score de similitud 0-1."""
    return max(0.0, 1.0 - distance)


@tool
def search_knowledge_base(query: str) -> str:
    """Busca en ChromaDB políticas de la tienda, FAQ, envíos, garantías."""
    settings = get_settings()
    collection = _get_collection()

    if collection.count() == 0:
        return (
            "La base de conocimiento aún no está cargada. "
            "Ejecuta: python -m ingest.load_docs"
        )

    embeddings = _get_embeddings()
    query_vector = embeddings.embed_query(query)

    results = collection.query(
        query_embeddings=[query_vector],
        n_results=3,
        include=["documents", "metadatas", "distances"],
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    if not documents:
        return "No encontré información confiable sobre esto en nuestra base de conocimiento."

    scored = [
        (_distance_to_score(dist), doc, meta.get("source", ""))
        for doc, meta, dist in zip(documents, metadatas, distances)
    ]
    scored.sort(key=lambda x: x[0], reverse=True)

    best_score = scored[0][0]
    if best_score < settings.rag_score_threshold:
        return "No encontré información confiable sobre esto en nuestra base de conocimiento."

    lines = ["*Información encontrada:*\n"]
    for score, doc, source in scored:
        if score < settings.rag_score_threshold:
            continue
        lines.append(f"📄 _{source}_ (relevancia: {score:.0%})\n{doc.strip()}\n")

    return "\n".join(lines).strip()
