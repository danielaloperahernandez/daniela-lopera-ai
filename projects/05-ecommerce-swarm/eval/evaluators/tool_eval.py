"""Evalúa corrección de tool calls (nombre + parámetros fuzzy)."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from eval.tracer import VALID_TOOLS

FUZZY_THRESHOLD = 0.8


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def fuzzy_match(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def _params_match(expected: dict, actual: dict) -> float:
    if not expected:
        return 1.0
    if not actual:
        return 0.0
    scores = []
    for key, exp_val in expected.items():
        act_val = actual.get(key, "")
        if isinstance(exp_val, (int, float)) and isinstance(act_val, (int, float)):
            scores.append(1.0 if exp_val == act_val else 0.0)
        else:
            scores.append(fuzzy_match(str(exp_val), str(act_val)))
    return sum(scores) / len(scores) if scores else 1.0


def evaluate_tools(
    tools_called: list[dict],
    expected_tools: list[str],
    expected_params: dict | None = None,
    optional_tools: bool = False,
) -> dict:
    """
    Score 0-1: nombres exactos + params fuzzy >= 0.8.
    Penaliza tools extra y tools fantasma.
    """
    actual_names = [t["name"] for t in tools_called]
    ghost_tools = [n for n in actual_names if n not in VALID_TOOLS]
    extra = [n for n in actual_names if n not in expected_tools]
    missing = [n for n in expected_tools if n not in actual_names]

    name_score = 0.0
    if expected_tools:
        matched = sum(1 for n in expected_tools if n in actual_names)
        name_score = matched / len(expected_tools)
        if not optional_tools and extra:
            name_score *= max(0.5, 1.0 - 0.15 * len(extra))
    elif not actual_names:
        name_score = 1.0
    elif optional_tools:
        name_score = 0.8

    param_score = 1.0
    if expected_params and expected_tools:
        for tool in tools_called:
            if tool["name"] in expected_tools:
                param_score = max(param_score, _params_match(expected_params, tool.get("params", {})))
                break

    if ghost_tools:
        name_score = 0.0

    score = round(min(1.0, name_score * 0.6 + param_score * 0.4), 3)

    return {
        "score": score,
        "passed": score >= FUZZY_THRESHOLD,
        "expected_tools": expected_tools,
        "actual_tools": actual_names,
        "missing_tools": missing,
        "extra_tools": extra,
        "ghost_tools": ghost_tools,
        "param_match": param_score,
    }
