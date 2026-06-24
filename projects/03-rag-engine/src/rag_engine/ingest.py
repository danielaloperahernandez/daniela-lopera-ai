"""Document ingestion: read files, chunk them, embed and store in Qdrant."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from langchain_text_splitters import RecursiveCharacterTextSplitter

from ai_core import VectorStore

SUPPORTED_SUFFIXES = {".md", ".txt"}


def _iter_files(paths: Iterable[Path]) -> Iterable[Path]:
    for path in paths:
        if path.is_dir():
            for sub in sorted(path.rglob("*")):
                if sub.suffix.lower() in SUPPORTED_SUFFIXES:
                    yield sub
        elif path.suffix.lower() in SUPPORTED_SUFFIXES:
            yield path


def ingest_paths(
    paths: Iterable[str | Path],
    *,
    chunk_size: int = 800,
    chunk_overlap: int = 120,
    recreate: bool = False,
    store: VectorStore | None = None,
) -> int:
    """Chunk + embed + upsert every supported file under ``paths``.

    Returns the number of chunks written. Set ``recreate=True`` to wipe the collection
    first (useful for a clean re-index during development).
    """
    store = store or VectorStore()
    store.ensure_collection(recreate=recreate)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    texts: list[str] = []
    metadatas: list[dict] = []
    for file in _iter_files(Path(p) for p in paths):
        content = file.read_text(encoding="utf-8", errors="ignore").strip()
        if not content:
            continue
        for idx, chunk in enumerate(splitter.split_text(content)):
            texts.append(chunk)
            metadatas.append({"source": file.name, "chunk": idx})

    if not texts:
        return 0
    return store.add_texts(texts, metadatas)
