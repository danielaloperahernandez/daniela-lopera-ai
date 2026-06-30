"""Evalúa que el nodo especializado visitado coincida con el esperado."""

from __future__ import annotations

from eval.mocks import SPECIALIZED_NODES


def evaluate_routing(nodes_visited: list[str], expected_node: str | list[str]) -> dict:
    """
    Compara el nodo esperado con los nodos visitados en el grafo.
    Acepta str o lista de nodos válidos (p.ej. orders + refunds).
    """
    expected_list = expected_node if isinstance(expected_node, list) else [expected_node]
    actual_specialized = [n for n in nodes_visited if n in SPECIALIZED_NODES]
    primary = actual_specialized[0] if actual_specialized else None
    passed = any(n in nodes_visited for n in expected_list)
    confidence = 1.0 if passed else (0.5 if primary else 0.0)

    return {
        "passed": passed,
        "expected": expected_list[0] if len(expected_list) == 1 else expected_list,
        "actual": primary or (nodes_visited[-1] if nodes_visited else "none"),
        "nodes_visited": nodes_visited,
        "confidence": confidence,
    }


def routing_accuracy_by_category(results: list[dict]) -> dict[str, float]:
    by_cat: dict[str, list[bool]] = {}
    for r in results:
        cat = r.get("category", "unknown")
        by_cat.setdefault(cat, []).append(r["passed"])
    return {cat: sum(v) / len(v) if v else 0.0 for cat, v in by_cat.items()}
