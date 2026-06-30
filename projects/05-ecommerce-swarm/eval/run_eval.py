#!/usr/bin/env python
"""
Script principal de evaluación del grafo e-commerce.

Uso:
    python eval/run_eval.py --report
    python eval/run_eval.py --quick
    python eval/run_eval.py --category rag --report
    python eval/run_eval.py --quick --report --ci   # gates CI (routing >=85%, judge >=7)
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REPORT_DIR = Path(__file__).parent / "reports"


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = int(len(s) * 0.95) - 1
    return s[max(0, min(idx, len(s) - 1))]


def _status(value: float, threshold: float, higher_is_better: bool = True) -> str:
    if higher_is_better:
        if value >= threshold:
            return "green"
        if value >= threshold * 0.9:
            return "yellow"
        return "red"
    if value <= threshold:
        return "green"
    if value <= threshold * 1.2:
        return "yellow"
    return "red"


def compute_metrics(results) -> dict:
    routing = results.routing
    tools = results.tools
    responses = results.responses
    halluc = results.hallucination
    latencies = results.latencies_ms

    routing_acc = sum(1 for r in routing if r["passed"]) / len(routing) if routing else 0.0
    tool_prec = sum(r["score"] for r in tools) / len(tools) if tools else 0.0
    avg_judge = sum(r["total"] for r in responses) / len(responses) if responses else 0.0
    hall_rate = sum(h["hallucination_rate"] for h in halluc) / len(halluc) if halluc else 0.0
    resolution = sum(1 for r in responses if r.get("passed")) / len(responses) if responses else 0.0

    by_cat: dict[str, list[bool]] = {}
    for r in routing:
        by_cat.setdefault(r["category"], []).append(r["passed"])
    cat_acc = {k: sum(v) / len(v) for k, v in by_cat.items()}

    return {
        "routing_accuracy": round(routing_acc, 3),
        "tool_precision": round(tool_prec, 3),
        "avg_judge_score": round(avg_judge, 2),
        "hallucination_rate": round(hall_rate, 3),
        "resolution_rate": round(resolution, 3),
        "latency_p95_ms": round(_p95(latencies), 1),
        "category_accuracy": cat_acc,
        "total_cases": len(routing),
    }


def print_console_summary(metrics: dict, exit_code: int) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    def icon(val: float, thr: float, hib: bool = True) -> str:
        return {"green": "[OK]", "yellow": "[!!]", "red": "[XX]"}[_status(val, thr, hib)]

    print("\n" + "=" * 55)
    print("  EVALUACION ECOMMERCE SWARM - RESUMEN")
    print("=" * 55)
    print(f"{icon(metrics['routing_accuracy'], 0.85)} Routing accuracy:    {metrics['routing_accuracy']:.1%}  (>=85%)")
    print(f"{icon(metrics['tool_precision'], 0.80)} Tool precision:      {metrics['tool_precision']:.1%}  (>=80%)")
    print(f"{icon(metrics['avg_judge_score'], 7.0)} Avg judge score:     {metrics['avg_judge_score']:.1f}/10 (>=7.0)")
    print(f"{icon(metrics['hallucination_rate'], 0.05, False)} Hallucination rate:  {metrics['hallucination_rate']:.1%}  (<=5%)")
    print(f"{icon(metrics['resolution_rate'], 0.85)} Resolution rate:     {metrics['resolution_rate']:.1%}  (>=85%)")
    print(f"    Latency P95:          {metrics['latency_p95_ms']:.0f} ms")
    print(f"    Casos evaluados:      {metrics['total_cases']}")
    print(f"{'[OK]' if exit_code == 0 else '[XX]'} Estado general:       {'PASS' if exit_code == 0 else 'FAIL'}")
    print("=" * 55 + "\n")


def generate_html_report(results, metrics: dict, mode: str) -> Path:
    from jinja2 import Template

    template_path = Path(__file__).parent / "report_template.html"
    template = Template(template_path.read_text(encoding="utf-8"))

    routing_map = {r["case_id"]: r for r in results.routing}
    tool_map = {r["case_id"]: r for r in results.tools}
    resp_map = {r["case_id"]: r for r in results.responses}
    hall_map = {r["case_id"]: r for r in results.hallucination}

    case_rows = []
    latencies = iter(results.latencies_ms)
    for rid, rr in routing_map.items():
        case_rows.append({
            "id": rid,
            "category": rr.get("category", ""),
            "routing_pass": rr["passed"],
            "tool_score": tool_map.get(rid, {}).get("score", "—"),
            "judge_score": resp_map.get(rid, {}).get("total", "—"),
            "hallucination_rate": hall_map.get(rid, {}).get("hallucination_rate", "—"),
            "latency_ms": round(next(latencies, 0), 1),
        })

    failures = [r for r in results.responses if not r.get("passed")]

    metrics_summary = [
        {"label": "Routing Accuracy", "value": f"{metrics['routing_accuracy']:.1%}", "threshold": "≥85%", "status": _status(metrics["routing_accuracy"], 0.85)},
        {"label": "Tool Precision", "value": f"{metrics['tool_precision']:.1%}", "threshold": "≥80%", "status": _status(metrics["tool_precision"], 0.80)},
        {"label": "Judge Score", "value": f"{metrics['avg_judge_score']}/10", "threshold": "≥7.0", "status": _status(metrics["avg_judge_score"], 7.0)},
        {"label": "Hallucination", "value": f"{metrics['hallucination_rate']:.1%}", "threshold": "≤5%", "status": _status(metrics["hallucination_rate"], 0.05, False)},
        {"label": "Resolution", "value": f"{metrics['resolution_rate']:.1%}", "threshold": "≥85%", "status": _status(metrics["resolution_rate"], 0.85)},
        {"label": "Latency P95", "value": f"{metrics['latency_p95_ms']:.0f} ms", "threshold": "—", "status": "green"},
    ]

    cats = list(metrics["category_accuracy"].keys())
    bar_chart = {
        "data": [{"type": "bar", "x": cats, "y": [metrics["category_accuracy"][c] for c in cats], "marker": {"color": "#3b82f6"}}],
        "layout": {"title": "Routing accuracy por categoría", "yaxis": {"tickformat": ".0%", "range": [0, 1]}},
    }

    radar_labels = ["Routing", "Tools", "Judge", "Resolution", "Low Halluc.", "Speed"]
    speed_score = max(0, min(1, 1 - metrics["latency_p95_ms"] / 5000))
    radar_values = [
        metrics["routing_accuracy"],
        metrics["tool_precision"],
        metrics["avg_judge_score"] / 10,
        metrics["resolution_rate"],
        1 - metrics["hallucination_rate"],
        speed_score,
    ]
    radar_chart = {
        "data": [{"type": "scatterpolar", "r": radar_values + [radar_values[0]], "theta": radar_labels + [radar_labels[0]], "fill": "toself", "name": "Eval"}],
        "layout": {"polar": {"radialaxis": {"visible": True, "range": [0, 1]}}, "title": "Radar — 6 métricas"},
    }

    html = template.render(
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        total_cases=metrics["total_cases"],
        mode=mode,
        metrics_summary=metrics_summary,
        case_rows=case_rows,
        failures=failures,
        edge_cases=results.edge_cases,
        bar_chart_json=json.dumps(bar_chart),
        radar_chart_json=json.dumps(radar_chart),
    )

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = REPORT_DIR / f"eval_report_{ts}.html"
    out.write_text(html, encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluación del grafo e-commerce")
    parser.add_argument("--quick", action="store_true", help="Solo 10 casos representativos")
    parser.add_argument("--category", choices=["rag", "ventas", "pedidos", "clientes", "reembolsos", "escalada"])
    parser.add_argument("--report", action="store_true", help="Generar reporte HTML")
    parser.add_argument("--ci", action="store_true", help="Fallar si métricas bajo umbral CI")
    args = parser.parse_args()

    from eval.dataset_builder import ensure_dataset
    from eval.regression_tracker import (
        check_ci_thresholds,
        compare_with_previous,
        print_regression_report,
        save_run,
    )
    from eval.results_collector import RESULTS

    ensure_dataset()

    # Limpiar resultados previos
    RESULTS.routing.clear()
    RESULTS.tools.clear()
    RESULTS.responses.clear()
    RESULTS.hallucination.clear()
    RESULTS.edge_cases.clear()
    RESULTS.latencies_ms.clear()

    import pytest

    eval_dir = Path(__file__).parent
    pytest_args = [
        str(eval_dir / "test_routing.py"),
        str(eval_dir / "test_tools.py"),
        str(eval_dir / "test_responses.py"),
        str(eval_dir / "test_edge_cases.py"),
        "-v",
        "--tb=short",
    ]
    if args.quick:
        pytest_args.append("--quick")
    if args.category:
        pytest_args.extend(["--category", args.category])

    exit_code = pytest.main(pytest_args)

    metrics = compute_metrics(RESULTS)
    mode = "quick" if args.quick else (args.category or "full")

    results_dict = RESULTS.to_dict()
    regression = compare_with_previous(metrics, results_dict)
    print_regression_report(regression)

    history_path = save_run(metrics, results_dict, mode=mode)
    print(f"[i] Historial guardado: {history_path.name}")

    print_console_summary(metrics, exit_code)

    if args.report:
        report_path = generate_html_report(RESULTS, metrics, mode)
        print(f"Reporte HTML: {report_path}")
        # Copia estable para CI artifact
        stable_report = REPORT_DIR / "eval_report_latest.html"
        stable_report.write_text(report_path.read_text(encoding="utf-8"), encoding="utf-8")

    # Guardar JSON de métricas
    metrics_path = REPORT_DIR / "last_metrics.json"
    REPORT_DIR.mkdir(exist_ok=True)
    metrics_path.write_text(
        json.dumps({"metrics": metrics, "results": results_dict, "regression": {
            "has_regression": regression.has_regression,
            "metric_regressions": regression.metric_regressions,
            "newly_failing_cases": regression.newly_failing_cases,
        }}, indent=2),
        encoding="utf-8",
    )

    if args.ci:
        ok, ci_errors = check_ci_thresholds(metrics)
        if not ok:
            print("\n[XX] CI gates failed:")
            for err in ci_errors:
                print(f"  - {err}")
            return 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
