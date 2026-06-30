"""Compara runs de evaluación y detecta regresiones vs el historial."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HISTORY_DIR = Path(__file__).parent / "history"
REGRESSION_THRESHOLD = 0.05  # 5 puntos porcentuales (proporciones 0–1)
JUDGE_REGRESSION_THRESHOLD = 5.0  # 5 puntos en escala /10

# Métricas donde mayor es mejor (resto: menor es mejor)
HIGHER_IS_BETTER = {
    "routing_accuracy",
    "tool_precision",
    "avg_judge_score",
    "resolution_rate",
}


@dataclass
class RegressionReport:
    has_regression: bool = False
    metric_regressions: list[dict] = field(default_factory=list)
    newly_failing_cases: list[dict] = field(default_factory=list)
    newly_passing_cases: list[dict] = field(default_factory=list)
    previous_run_id: str | None = None
    current_run_id: str | None = None


def _case_overall_pass(case_id: str, results: dict) -> bool:
    routing = {r["case_id"]: r for r in results.get("routing", [])}
    tools = {r["case_id"]: r for r in results.get("tools", [])}
    responses = {r["case_id"]: r for r in results.get("responses", [])}

    if case_id not in routing:
        return False
    ok_r = routing[case_id].get("passed", False)
    ok_t = tools.get(case_id, {}).get("passed", True) if case_id in tools else True
    ok_j = responses.get(case_id, {}).get("passed", False) if case_id in responses else True
    return ok_r and ok_t and ok_j


def build_case_summary(results: dict) -> dict[str, dict]:
    """Resumen pass/fail por caso para persistir en historial."""
    routing = {r["case_id"]: r for r in results.get("routing", [])}
    tools = {r["case_id"]: r for r in results.get("tools", [])}
    responses = {r["case_id"]: r for r in results.get("responses", [])}
    all_ids = set(routing) | set(tools) | set(responses)

    summary = {}
    for cid in sorted(all_ids):
        summary[cid] = {
            "routing_pass": routing.get(cid, {}).get("passed", False),
            "tool_pass": tools.get(cid, {}).get("passed", True),
            "response_pass": responses.get(cid, {}).get("passed", False),
            "overall_pass": _case_overall_pass(cid, results),
            "category": routing.get(cid, {}).get("category")
            or tools.get(cid, {}).get("category")
            or responses.get(cid, {}).get("category", ""),
        }
    return summary


def save_run(
    metrics: dict,
    results: dict,
    mode: str = "full",
    history_dir: Path | None = None,
) -> Path:
    """Guarda snapshot del run en eval/history/."""
    history_dir = history_dir or HISTORY_DIR
    history_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_id = f"run_{ts}_{mode}"
    payload = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "metrics": metrics,
        "cases": build_case_summary(results),
        "results": results,
    }
    path = history_dir / f"{run_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # Puntero al último run
    (history_dir / "latest.json").write_text(
        json.dumps({"run_id": run_id, "path": path.name}, indent=2),
        encoding="utf-8",
    )
    return path


def _load_previous_run(history_dir: Path) -> dict | None:
    latest_ptr = history_dir / "latest.json"
    if not latest_ptr.exists():
        runs = sorted(history_dir.glob("run_*.json"), key=lambda p: p.stat().st_mtime)
        if len(runs) < 2:
            return None
        # Comparar contra el penúltimo (el último aún no guardado en compare)
        return json.loads(runs[-2].read_text(encoding="utf-8"))

    ptr = json.loads(latest_ptr.read_text(encoding="utf-8"))
    prev_path = history_dir / ptr["path"]
    if prev_path.exists():
        return json.loads(prev_path.read_text(encoding="utf-8"))
    return None


def _metric_delta(name: str, prev: float, curr: float) -> dict:
    higher_better = name in HIGHER_IS_BETTER
    threshold = JUDGE_REGRESSION_THRESHOLD if name == "avg_judge_score" else REGRESSION_THRESHOLD
    if higher_better:
        dropped = prev - curr
        regressed = dropped > threshold
    else:
        dropped = curr - prev
        regressed = dropped > threshold

    return {
        "metric": name,
        "previous": prev,
        "current": curr,
        "delta": round(curr - prev, 4),
        "delta_pp": round((curr - prev) * 100, 2) if name != "avg_judge_score" else round(curr - prev, 2),
        "regressed": regressed,
        "direction": "higher_is_better" if higher_better else "lower_is_better",
    }


def compare_with_previous(
    metrics: dict,
    results: dict,
    history_dir: Path | None = None,
) -> RegressionReport:
    """
    Compara métricas y casos contra el run anterior en eval/history/.
    Alerta si alguna métrica cayó más de 5 pp (o 5 puntos en judge /10).
    """
    history_dir = history_dir or HISTORY_DIR
    report = RegressionReport()

    previous = _load_previous_run(history_dir)
    if not previous:
        return report

    report.previous_run_id = previous.get("run_id")
    prev_metrics = previous.get("metrics", {})
    prev_cases = previous.get("cases", {})
    curr_cases = build_case_summary(results)

    for key in (
        "routing_accuracy",
        "tool_precision",
        "avg_judge_score",
        "resolution_rate",
        "hallucination_rate",
    ):
        if key not in prev_metrics or key not in metrics:
            continue
        delta = _metric_delta(key, float(prev_metrics[key]), float(metrics[key]))
        if delta["regressed"]:
            report.metric_regressions.append(delta)
            report.has_regression = True

    for cid, prev in prev_cases.items():
        curr = curr_cases.get(cid)
        if not curr:
            continue
        if prev.get("overall_pass") and not curr.get("overall_pass"):
            report.newly_failing_cases.append(
                {
                    "case_id": cid,
                    "category": curr.get("category", ""),
                    "before": prev,
                    "after": curr,
                }
            )
            report.has_regression = True
        elif not prev.get("overall_pass") and curr.get("overall_pass"):
            report.newly_passing_cases.append({"case_id": cid, "category": curr.get("category", "")})

    return report


def print_regression_report(report: RegressionReport) -> None:
    if not report.previous_run_id:
        print("\n[i] Sin run anterior en eval/history/ — baseline establecido.\n")
        return

    print("\n" + "=" * 55)
    print("  REGRESSION TRACKER")
    print("=" * 55)
    print(f"  Run anterior: {report.previous_run_id}")

    if report.metric_regressions:
        print("\n  [!] Regresiones de metricas (>5 pp / 5 pts):")
        for m in report.metric_regressions:
            unit = "pp" if m["metric"] != "avg_judge_score" else "pts"
            print(
                f"    - {m['metric']}: {m['previous']:.3f} -> {m['current']:.3f} "
                f"({m['delta_pp']:+.2f} {unit})"
            )

    if report.newly_failing_cases:
        print("\n  [!] Casos que PASABAN y ahora FALLAN:")
        for c in report.newly_failing_cases:
            b, a = c["before"], c["after"]
            print(
                f"    - {c['case_id']} ({c['category']}): "
                f"routing={a['routing_pass']} tools={a['tool_pass']} judge={a['response_pass']}"
            )

    if report.newly_passing_cases:
        print("\n  [+] Casos que fallaban y ahora pasan:")
        for c in report.newly_passing_cases:
            print(f"    - {c['case_id']} ({c['category']})")

    if not report.has_regression:
        print("\n  [OK] Sin regresiones respecto al run anterior.")
    print("=" * 55 + "\n")


def check_ci_thresholds(metrics: dict) -> tuple[bool, list[str]]:
    """Umbrales para CI: routing >= 0.85, judge >= 7.0."""
    errors = []
    if metrics.get("routing_accuracy", 0) < 0.85:
        errors.append(f"routing_accuracy {metrics['routing_accuracy']:.1%} < 85%")
    if metrics.get("avg_judge_score", 0) < 7.0:
        errors.append(f"avg_judge_score {metrics.get('avg_judge_score', 0):.1f} < 7.0")
    return len(errors) == 0, errors
