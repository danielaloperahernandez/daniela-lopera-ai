"""Acumulador global de resultados para pytest y run_eval.py."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvalResults:
    routing: list[dict] = field(default_factory=list)
    tools: list[dict] = field(default_factory=list)
    responses: list[dict] = field(default_factory=list)
    hallucination: list[dict] = field(default_factory=list)
    edge_cases: list[dict] = field(default_factory=list)
    latencies_ms: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "routing": self.routing,
            "tools": self.tools,
            "responses": self.responses,
            "hallucination": self.hallucination,
            "edge_cases": self.edge_cases,
            "latencies_ms": self.latencies_ms,
        }


RESULTS = EvalResults()
