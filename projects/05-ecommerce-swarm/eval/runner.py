"""Ejecuta un caso del dataset contra el grafo y retorna traza completa."""

from __future__ import annotations

import time
from typing import Any

from langchain_core.messages import HumanMessage

from eval.mocks import TEST_PHONE, build_eval_graph, set_current_tracer
from eval.tracer import EvalTracer, get_tool_log, reset_tool_log


async def run_case(case: dict, tracer: EvalTracer | None = None) -> dict[str, Any]:
    case_id = case["id"]
    run_tracer = tracer or EvalTracer(run_id=case_id)
    run_tracer.start_case(case_id)

    graph = build_eval_graph()

    messages = []
    for turn in case.get("conversation", []):
        if turn["role"] == "user":
            messages.append(HumanMessage(content=turn["content"]))

    state = {
        "messages": messages,
        "phone": case.get("phone", TEST_PHONE),
        "intent": "",
        "shopify_customer_id": "",
        "attempts": 0,
        "requires_human": False,
        "final_response": "",
        "message_id": f"eval_{case_id}",
        "needs_refund": False,
    }

    t0 = time.perf_counter()
    reset_tool_log()
    set_current_tracer(run_tracer)
    try:
        result = await graph.ainvoke(state)
    finally:
        set_current_tracer(None)
    latency_ms = (time.perf_counter() - t0) * 1000

    query = case["conversation"][-1]["content"]
    trace = run_tracer.end_case({"response": result.get("final_response", "")})

    return {
        "case_id": case_id,
        "category": case.get("category"),
        "difficulty": case.get("difficulty"),
        "query": query,
        "response": result.get("final_response", ""),
        "nodes_visited": trace["nodes"],
        "tools_called": get_tool_log(),
        "latency_ms": latency_ms,
        "expected": case.get("expected", {}),
    }
