"""Ingestion should read supported files, chunk them and upsert with metadata."""

from __future__ import annotations

from pathlib import Path

from rag_engine.ingest import ingest_paths


def test_ingest_chunks_and_stores(tmp_path: Path, fake_store) -> None:
    doc = tmp_path / "note.md"
    doc.write_text("Sentence one. " * 200, encoding="utf-8")

    count = ingest_paths([tmp_path], store=fake_store, chunk_size=200, chunk_overlap=20)

    assert count > 1  # long doc must produce multiple chunks
    assert count == len(fake_store.texts)
    assert fake_store.ensured is True
    assert all(meta["source"] == "note.md" for meta in fake_store.metadatas)


def test_ingest_ignores_unsupported_files(tmp_path: Path, fake_store) -> None:
    (tmp_path / "image.png").write_bytes(b"\x89PNG")
    (tmp_path / "readme.txt").write_text("hello world", encoding="utf-8")

    count = ingest_paths([tmp_path], store=fake_store)

    assert count == 1
    assert fake_store.metadatas[0]["source"] == "readme.txt"


def test_ingest_empty_returns_zero(tmp_path: Path, fake_store) -> None:
    assert ingest_paths([tmp_path], store=fake_store) == 0
