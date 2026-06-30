"""
Script de ingesta de documentos en ChromaDB.
Ejecutar desde la raíz del proyecto:

    python -m ingest.load_docs
"""

from tools.knowledge_base import DOCS_DIR, ingest_docs


def main() -> None:
    count = ingest_docs()
    print(f"✓ Ingestados {count} chunks desde {DOCS_DIR}")
    if count == 0:
        print("  ⚠ No se encontraron archivos .txt en data/sample_docs/")


if __name__ == "__main__":
    main()
