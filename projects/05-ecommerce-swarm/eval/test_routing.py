"""Tests de routing accuracy por caso del dataset."""

from __future__ import annotations

import pytest

from eval.evaluators.routing_eval import evaluate_routing, routing_accuracy_by_category
from eval.results_collector import RESULTS


def pytest_generate_tests(metafunc):
    if "case" in metafunc.fixturenames and metafunc.definition.name == "test_routing_case":
        from eval.dataset_builder import load_dataset

        quick = metafunc.config.getoption("--quick")
        category = metafunc.config.getoption("--category")
        cases = load_dataset(quick=quick, category=category or None)
        metafunc.parametrize("case", cases, ids=[c["id"] for c in cases])


@pytest.mark.asyncio
async def test_routing_case(case, run_case_fn):
    run = await run_case_fn(case)
    exp = case["expected"]
    result = evaluate_routing(run["nodes_visited"], exp.get("node", exp.get("nodes", "rag_node")))
    record = {
        "case_id": case["id"],
        "category": case["category"],
        "difficulty": case["difficulty"],
        "passed": result["passed"],
        "expected": result["expected"],
        "actual": result["actual"],
        "confidence": result["confidence"],
        "nodes_visited": run["nodes_visited"],
    }
    RESULTS.routing.append(record)
    RESULTS.latencies_ms.append(run["latency_ms"])
    assert result["passed"], f"Routing: expected {exp['node']}, got {run['nodes_visited']}"


def test_routing_accuracy_by_category():
    if not RESULTS.routing:
        pytest.skip("Sin resultados de routing")
    acc = routing_accuracy_by_category(RESULTS.routing)
    for cat, score in acc.items():
        if len([r for r in RESULTS.routing if r.get("category") == cat]) < 2:
            continue  # categorías con 1 caso en --quick no bloquean
        assert score >= 0.85, f"Routing accuracy {cat}={score:.2%} < 85%"
