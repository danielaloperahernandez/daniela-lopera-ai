"""Tests de calidad de respuesta con LLM-as-judge."""

from __future__ import annotations

import pytest

from eval.evaluators.hallucination_eval import evaluate_hallucination
from eval.evaluators.response_eval import PASS_THRESHOLD, evaluate_response
from eval.results_collector import RESULTS


def pytest_generate_tests(metafunc):
    if "case" in metafunc.fixturenames and metafunc.definition.name == "test_response_case":
        from eval.dataset_builder import load_dataset

        quick = metafunc.config.getoption("--quick")
        category = metafunc.config.getoption("--category")
        cases = load_dataset(quick=quick, category=category or None)
        metafunc.parametrize("case", cases, ids=[c["id"] for c in cases])


@pytest.mark.asyncio
async def test_response_case(case, run_case_fn, gemini_judge):
    run = await run_case_fn(case)
    exp = case["expected"]
    judge = await evaluate_response(
        query=run["query"],
        response=run["response"],
        judge_criteria=exp.get("judge_criteria", ""),
        must_contain=exp.get("response_must_contain", []),
        must_not_contain=exp.get("response_must_not_contain", []),
        llm=gemini_judge,
    )
    record = {
        "case_id": case["id"],
        "category": case["category"],
        "total": judge.get("total", 0),
        "passed": judge.get("passed", False),
        "feedback": judge.get("feedback", ""),
        "scores": judge.get("scores", {}),
        "mode": judge.get("mode", "unknown"),
    }
    RESULTS.responses.append(record)

    hall = await evaluate_hallucination(run["response"], llm=gemini_judge)
    RESULTS.hallucination.append({"case_id": case["id"], **hall})

    assert judge.get("total", 0) >= PASS_THRESHOLD, (
        f"Judge score {judge.get('total')} < {PASS_THRESHOLD}: {judge.get('feedback')}"
    )


def test_average_judge_score():
    if not RESULTS.responses:
        pytest.skip("Sin resultados de respuestas")
    avg = sum(r["total"] for r in RESULTS.responses) / len(RESULTS.responses)
    assert avg >= PASS_THRESHOLD, f"Score promedio {avg:.2f} < {PASS_THRESHOLD}"
