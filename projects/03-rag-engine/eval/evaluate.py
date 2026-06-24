"""Evaluation harness for the RAG engine.

Runs every question in ``dataset.jsonl`` through the pipeline and scores the results on
three metrics that matter for RAG quality:

  - correctness  : does the answer match the ground truth? (LLM-as-judge, 0..1)
  - faithfulness : is the answer supported by the retrieved context? (LLM-as-judge, 0..1)
  - abstention   : for unanswerable questions, did the system correctly refuse? (0/1)

It prints a per-question table and an aggregate summary, and writes ``eval/report.json``.

Usage:
    python eval/evaluate.py
    python eval/evaluate.py --dataset eval/dataset.jsonl

Note: this is a lightweight, self-contained judge so the project runs with no extra deps.
For a heavier industry-standard option, the same dataset can be fed to Ragas
(faithfulness / answer_relevancy / context_precision) - see the project README.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import BaseModel, Field

# Make `rag_engine` importable when run as a script from the project root.
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_core import structured_chat  # noqa: E402
from rag_engine import RAGPipeline  # noqa: E402


class JudgeScore(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    reason: str


_CORRECTNESS_SYS = (
    "You are a strict grader. Compare a candidate answer to the reference answer for the "
    "same question. Output a score from 0 to 1 for how well the candidate matches the "
    "reference in meaning (1 = fully correct, 0 = wrong/irrelevant). Ignore wording."
)
_FAITHFULNESS_SYS = (
    "You judge whether a candidate answer is supported by the provided context. Output 1 "
    "if every claim in the answer is grounded in the context, 0 if it contains unsupported "
    "claims. An explicit 'not enough information' answer is faithful (score 1)."
)


def _judge_correctness(question: str, candidate: str, reference: str) -> JudgeScore:
    user = f"Question: {question}\n\nReference: {reference}\n\nCandidate: {candidate}"
    return structured_chat(JudgeScore, _CORRECTNESS_SYS, user, temperature=0.0)


def _judge_faithfulness(candidate: str, context: str) -> JudgeScore:
    user = f"Context:\n{context}\n\nCandidate answer: {candidate}"
    return structured_chat(JudgeScore, _FAITHFULNESS_SYS, user, temperature=0.0)


def evaluate(dataset_path: Path) -> dict:
    rows = [
        json.loads(line)
        for line in dataset_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    pipeline = RAGPipeline()

    results = []
    for row in rows:
        question = row["question"]
        result = pipeline.ask(question)
        context = "\n\n".join(s.snippet for s in result.sources)

        if row.get("expected_answerable", True):
            correctness = _judge_correctness(question, result.answer, row["ground_truth"])
            faithfulness = _judge_faithfulness(result.answer, context)
            abstention = None
            correctness_score = correctness.score
            faithfulness_score = faithfulness.score
        else:
            # Unanswerable: the right behaviour is to refuse.
            abstention = 0.0 if result.answered else 1.0
            correctness_score = None
            faithfulness_score = None

        results.append(
            {
                "question": question,
                "answer": result.answer,
                "answered": result.answered,
                "confidence": result.confidence,
                "correctness": correctness_score,
                "faithfulness": faithfulness_score,
                "abstention": abstention,
            }
        )

    summary = _summarize(results)
    return {"summary": summary, "results": results}


def _avg(values: list[float]) -> float | None:
    vals = [v for v in values if v is not None]
    return round(sum(vals) / len(vals), 3) if vals else None


def _summarize(results: list[dict]) -> dict:
    return {
        "n": len(results),
        "correctness": _avg([r["correctness"] for r in results]),
        "faithfulness": _avg([r["faithfulness"] for r in results]),
        "abstention": _avg([r["abstention"] for r in results]),
    }


def _print_report(report: dict) -> None:
    print("\n=== Per-question results ===")
    header = f"{'correct':>8} {'faith':>6} {'abst':>5}  question"
    print(header)
    print("-" * len(header))
    for r in report["results"]:
        c = "  -  " if r["correctness"] is None else f"{r['correctness']:.2f}"
        f = "  -  " if r["faithfulness"] is None else f"{r['faithfulness']:.2f}"
        a = "  -  " if r["abstention"] is None else f"{r['abstention']:.0f}"
        print(f"{c:>8} {f:>6} {a:>5}  {r['question'][:60]}")

    s = report["summary"]
    print("\n=== Summary ===")
    print(f"  questions   : {s['n']}")
    print(f"  correctness : {s['correctness']}")
    print(f"  faithfulness: {s['faithfulness']}")
    print(f"  abstention  : {s['abstention']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the RAG engine")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path(__file__).parent / "dataset.jsonl",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).parent / "report.json",
    )
    args = parser.parse_args()

    report = evaluate(args.dataset)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    _print_report(report)
    print(f"\nReport written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
