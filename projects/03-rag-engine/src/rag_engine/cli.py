"""Command-line interface for the RAG engine.

    python -m rag_engine.cli ingest data/knowledge --recreate
    python -m rag_engine.cli ask "What distance metric does the store use?"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .ingest import ingest_paths
from .pipeline import RAGPipeline


def _cmd_ingest(args: argparse.Namespace) -> int:
    count = ingest_paths(args.paths, recreate=args.recreate)
    print(f"Ingested {count} chunks from {len(args.paths)} path(s).")
    return 0 if count else 1


def _cmd_ask(args: argparse.Namespace) -> int:
    pipeline = RAGPipeline(top_k=args.top_k)
    result = pipeline.ask(args.question)
    if args.json:
        print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))
    else:
        print(f"\nQ: {result.question}")
        print(f"A: {result.answer}")
        print(f"   (answered={result.answered}, confidence={result.confidence:.2f})")
        print("\nSources:")
        for s in result.sources:
            print(f"  - {s.source} (score={s.score}): {s.snippet[:80]}...")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rag_engine", description="RAG engine CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ingest = sub.add_parser("ingest", help="Chunk, embed and store documents")
    p_ingest.add_argument("paths", nargs="+", type=Path, help="Files or directories")
    p_ingest.add_argument("--recreate", action="store_true", help="Wipe collection first")
    p_ingest.set_defaults(func=_cmd_ingest)

    p_ask = sub.add_parser("ask", help="Ask a question against the knowledge base")
    p_ask.add_argument("question", help="The question to answer")
    p_ask.add_argument("--top-k", type=int, default=4, help="Chunks to retrieve")
    p_ask.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    p_ask.set_defaults(func=_cmd_ask)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
