"""Trazabilidad LangSmith o FakeTracer offline."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

TRACES_DIR = Path(__file__).parent / "traces"
VALID_TOOLS = {
    "search_knowledge_base",
    "search_products",
    "get_product_detail",
    "get_order_by_number",
    "get_customer_orders",
    "get_customer_by_phone",
    "create_refund",
}

_tool_log: list[dict] = []


def get_tool_log() -> list[dict]:
    return _tool_log


def reset_tool_log() -> None:
    _tool_log.clear()


@dataclass
class EvalTracer:
    """Captura nodos, tools y latencia. Integra LangSmith si hay API key."""

    run_id: str
    nodes: list[str] = field(default_factory=list)
    latencies_ms: list[float] = field(default_factory=list)
    langsmith_enabled: bool = False
    _ls_run: Any = None
    _start: float = 0.0

    def __post_init__(self) -> None:
        self.langsmith_enabled = bool(os.environ.get("LANGSMITH_API_KEY"))
        TRACES_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def config(self) -> dict:
        if not self.langsmith_enabled:
            return {}
        try:
            from langsmith.run_helpers import tracing_context

            return {
                "run_name": self.run_id,
                "tags": ["ecommerce-eval"],
            }
        except ImportError:
            return {}

    def start_case(self, case_id: str) -> None:
        self._start = time.perf_counter()
        reset_tool_log()
        if self.langsmith_enabled:
            try:
                from langsmith import Client

                client = Client()
                project = os.environ.get("LANGSMITH_PROJECT", "ecommerce-eval")
                self._ls_run = client.create_run(
                    name=case_id,
                    run_type="chain",
                    inputs={"case_id": case_id},
                    project_name=project,
                )
            except Exception:
                self.langsmith_enabled = False

    def record_node(self, name: str) -> None:
        self.nodes.append(name)

    def end_case(self, outputs: dict) -> dict:
        elapsed = (time.perf_counter() - self._start) * 1000
        self.latencies_ms.append(elapsed)
        trace = {
            "run_id": self.run_id,
            "nodes": list(self.nodes),
            "tools": list(get_tool_log()),
            "latency_ms": elapsed,
            "outputs": outputs,
        }
        trace_path = TRACES_DIR / f"{self.run_id}.json"
        trace_path.write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")

        if self.langsmith_enabled and self._ls_run:
            try:
                from langsmith import Client

                Client().update_run(self._ls_run.id, outputs=outputs)
            except Exception:
                pass

        self.nodes.clear()
        return trace

    @classmethod
    def create_experiment(cls, name: str) -> "EvalTracer":
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "true" if os.environ.get("LANGSMITH_API_KEY") else "false")
        os.environ.setdefault("LANGCHAIN_PROJECT", os.environ.get("LANGSMITH_PROJECT", "ecommerce-eval"))
        return cls(run_id=name)
