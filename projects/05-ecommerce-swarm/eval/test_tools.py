"""Tests de corrección de tool calls."""

from __future__ import annotations

import pytest

from eval.evaluators.tool_eval import evaluate_tools
from eval.results_collector import RESULTS


def pytest_generate_tests(metafunc):
    if "case" in metafunc.fixturenames and metafunc.definition.name == "test_tool_case":
        from eval.dataset_builder import load_dataset

        quick = metafunc.config.getoption("--quick")
        category = metafunc.config.getoption("--category")
        cases = load_dataset(quick=quick, category=category or None)
        metafunc.parametrize("case", cases, ids=[c["id"] for c in cases])


@pytest.mark.asyncio
async def test_tool_case(case, run_case_fn):
    run = await run_case_fn(case)
    exp = case["expected"]
    optional = exp["node"] in ("escalation_node", "saludo_directo")
    result = evaluate_tools(
        run["tools_called"],
        exp.get("tools_called", []),
        exp.get("tool_params"),
        optional_tools=optional or not exp.get("tools_called"),
    )
    record = {"case_id": case["id"], "category": case["category"], **result}
    RESULTS.tools.append(record)
    assert result["score"] >= 0.8, (
        f"Tool score {result['score']}: expected {exp.get('tools_called')}, "
        f"got {result['actual_tools']}, ghost={result['ghost_tools']}"
    )


def test_tool_precision_global():
    if not RESULTS.tools:
        pytest.skip("Sin resultados de tools")
    avg = sum(r["score"] for r in RESULTS.tools) / len(RESULTS.tools)
    ghosts = sum(len(r.get("ghost_tools", [])) for r in RESULTS.tools)
    assert ghosts == 0, f"Tools fantasma detectadas: {ghosts}"
    assert avg >= 0.80, f"Tool precision global {avg:.2%} < 80%"
