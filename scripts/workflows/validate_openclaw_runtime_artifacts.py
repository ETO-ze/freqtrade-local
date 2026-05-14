from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DEFAULT_RELATIVE_PATHS = [
    "dashboard-data/backtest.json",
    "dashboard-data/alerts.json",
    "reports/openclaw-daily-alt-ml-stable.json",
    "reports/openclaw-auto-backtest-latest.json",
    "reports/openclaw-auto-approval-latest.json",
    "reports/openclaw-dynamic-alt-universe.json",
    "reports/openclaw-approved-history.json",
    "reports/openclaw-server-status-latest.json",
    "reports/daemon/factor-daemon-fast-status.json",
    "reports/daemon/factor-daemon-stable-status.json",
    "reports/daemon/factor-daemon-autotune-status.json",
]

DEFAULT_REPORT_JSON = "reports/openclaw-runtime-validation-latest.json"
DEFAULT_REPORT_MD = "reports/openclaw-runtime-validation-latest.md"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, "", "N/A", "n/a"):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
    return None


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    json.loads(text)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def validate_path(path: Path, required: bool) -> tuple[bool, dict[str, Any]]:
    if not path.exists():
        return (not required), {
            "path": str(path),
            "status": "missing",
            "required": required,
            "message": f"missing: {path}",
        }
    try:
        payload = load_json(path)
    except Exception as exc:
        return False, {
            "path": str(path),
            "status": "invalid",
            "required": required,
            "message": f"invalid json: {path} ({exc})",
            "error": str(exc),
        }
    kind = type(payload).__name__
    size = path.stat().st_size
    return True, {
        "path": str(path),
        "status": "ok",
        "required": required,
        "message": f"ok: {path} [{kind}, {size} bytes]",
        "kind": kind,
        "size_bytes": size,
    }


def add_issue(issues: list[dict[str, Any]], severity: str, title: str, detail: str) -> None:
    issues.append({"severity": severity, "title": title, "detail": detail})


def analyze_backtest(root: Path, issues: list[dict[str, Any]]) -> dict[str, Any]:
    path = root / "dashboard-data/backtest.json"
    if not path.exists():
        add_issue(issues, "warning", "dashboard backtest missing", "dashboard-data/backtest.json does not exist.")
        return {}
    payload = load_json(path)
    metrics = payload.get("metrics") or {}
    active = payload.get("active_factor") or {}
    candidate = payload.get("latest_candidate") or {}
    active_metrics = active.get("metrics") or metrics
    top_factors = payload.get("top_factors") or []
    mark_premium_weight = sum(
        safe_float(item.get("WeightedImportance"))
        for item in top_factors
        if "mark_premium" in str(item.get("Feature") or "")
    )
    max_drawdown = safe_float(active_metrics.get("max_drawdown_pct"))
    candidate_metrics = candidate.get("metrics") or {}
    candidate_profit = safe_float(candidate_metrics.get("total_profit_pct"))

    if mark_premium_weight >= 0.6:
        add_issue(
            issues,
            "warning",
            "mark premium feature family dominates active factor",
            f"mark_premium family weight is {mark_premium_weight:.4f}; add family cap or ablation before trusting generalization.",
        )
    if max_drawdown >= 25:
        add_issue(
            issues,
            "warning",
            "active factor is high drawdown",
            f"active max drawdown is {max_drawdown:.2f}%; keep it in high-risk channel and avoid calling it stable.",
        )
    if candidate_profit and candidate_profit < safe_float(active_metrics.get("total_profit_pct")) * 0.7:
        add_issue(
            issues,
            "info",
            "latest candidate weaker than active",
            f"candidate profit {candidate_profit:.2f}% is materially below active profit {safe_float(active_metrics.get('total_profit_pct')):.2f}%.",
        )

    approval = payload.get("approval") or {}
    gate = approval.get("gate_breakdown") or {}
    failed_gate_checks: list[str] = []
    for group_name in ("standard_checks", "experimental_checks"):
        for check in gate.get(group_name) or []:
            if isinstance(check, dict) and not bool(check.get("passed")):
                failed_gate_checks.append(f"{group_name}.{check.get('name')}")

    return {
        "strategy": payload.get("strategy"),
        "generated_at": payload.get("generated_at"),
        "active_factor": {
            "generated_at": active.get("generated_at"),
            "best_model": active.get("best_model"),
            "approval_mode": active.get("approval_mode"),
            "metrics": active_metrics,
            "selected_pairs": active.get("selected_pairs") or payload.get("selected_pairs") or [],
        },
        "latest_candidate": candidate,
        "approval": {
            "decision": approval.get("decision"),
            "approved_for_sync": approval.get("approved_for_sync"),
            "approval_mode": approval.get("approval_mode"),
            "failed_gate_checks": failed_gate_checks,
        },
        "mark_premium_weight": round(mark_premium_weight, 6),
        "top_factors": top_factors[:8],
    }


def analyze_dynamic_universe(root: Path, issues: list[dict[str, Any]]) -> dict[str, Any]:
    path = root / "reports/openclaw-dynamic-alt-universe.json"
    if not path.exists():
        add_issue(issues, "info", "dynamic universe missing", f"{path} does not exist.")
        return {}
    payload = load_json(path)
    pools = payload.get("pools") or {}
    pool_counts = {name: len(pairs or []) for name, pairs in pools.items() if isinstance(pairs, list)}
    if pools and pool_counts.get("core", 0) == 0:
        add_issue(
            issues,
            "warning",
            "dynamic universe core pool empty",
            "core pool is empty; candidate config will need fallback and promotion quality may be weak.",
        )
    return {
        "generated_at": payload.get("generated_at"),
        "freshest_market_timestamp": payload.get("freshest_market_timestamp"),
        "top_n": payload.get("top_n"),
        "core_n": payload.get("core_n"),
        "expand_n": payload.get("expand_n"),
        "pool_counts": pool_counts,
        "selected_pairs": payload.get("selected_pairs") or [],
    }


def analyze_daemons(root: Path, issues: list[dict[str, Any]], max_running_minutes: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    now = datetime.now()
    for name in ("fast", "stable", "evolution", "autotune"):
        path = root / "reports" / "daemon" / f"factor-daemon-{name}-status.json"
        if not path.exists():
            add_issue(issues, "info", f"{name} daemon status missing", f"{path} does not exist.")
            continue
        payload = load_json(path)
        started = parse_datetime(payload.get("started_at"))
        completed = parse_datetime(payload.get("completed_at"))
        status = str(payload.get("status") or "")
        running_minutes = None
        if status == "running" and started:
            running_minutes = max(0.0, (now - started.replace(tzinfo=None)).total_seconds() / 60)
            if running_minutes > max_running_minutes:
                add_issue(
                    issues,
                    "warning",
                    f"{name} daemon may be stale",
                    f"status is running for {running_minutes:.1f} minutes; threshold is {max_running_minutes} minutes.",
                )
        if status == "error":
            add_issue(
                issues,
                "critical",
                f"{name} daemon error",
                str(payload.get("error") or payload.get("note") or "status is error"),
            )
        results.append(
            {
                "name": name,
                "status": status,
                "run": payload.get("run"),
                "started_at": payload.get("started_at"),
                "completed_at": payload.get("completed_at"),
                "running_minutes": round(running_minutes, 2) if running_minutes is not None else None,
                "note": payload.get("note"),
            }
        )
    return results


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# OpenClaw Runtime Validation",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Overall status: {payload['status']}",
        "",
        "## Issues",
    ]
    issues = payload.get("issues") or []
    if not issues:
        lines.append("- none")
    for issue in issues:
        lines.append(f"- {issue['severity']}: {issue['title']} - {issue['detail']}")

    backtest = payload.get("backtest") or {}
    active = backtest.get("active_factor") or {}
    metrics = active.get("metrics") or {}
    approval = backtest.get("approval") or {}
    dynamic_universe = payload.get("dynamic_universe") or {}
    lines.extend(
        [
            "",
            "## Active Factor",
            f"- Model: {active.get('best_model') or 'N/A'}",
            f"- Approval mode: {active.get('approval_mode') or 'N/A'}",
            f"- Profit: {metrics.get('total_profit_pct', 'N/A')}%",
            f"- PF: {metrics.get('profit_factor', 'N/A')}",
            f"- Winrate: {metrics.get('winrate', 'N/A')}%",
            f"- Drawdown: {metrics.get('max_drawdown_pct', 'N/A')}%",
            f"- Trades: {metrics.get('trade_count', 'N/A')}",
            f"- Mark premium family weight: {backtest.get('mark_premium_weight', 'N/A')}",
            "",
            "## Latest Approval",
            f"- Decision: {approval.get('decision') or 'N/A'}",
            f"- Approved for sync: {approval.get('approved_for_sync')}",
            f"- Approval mode: {approval.get('approval_mode') or 'N/A'}",
            f"- Failed gate checks: {', '.join(approval.get('failed_gate_checks') or []) or 'none'}",
            "",
            "## Dynamic Universe",
            f"- Generated: {dynamic_universe.get('generated_at') or 'N/A'}",
            f"- Freshest market timestamp: {dynamic_universe.get('freshest_market_timestamp') or 'N/A'}",
            f"- Pool counts: {dynamic_universe.get('pool_counts') or {}}",
            "",
            "## Daemons",
        ]
    )
    for daemon in payload.get("daemons") or []:
        lines.append(
            f"- {daemon['name']}: {daemon.get('status')} | run={daemon.get('run')} | started={daemon.get('started_at')} | completed={daemon.get('completed_at')}"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate OpenClaw runtime JSON artifacts.")
    parser.add_argument(
        "--project-root",
        default=str(Path(__file__).resolve().parents[2]),
        help="Project root. Defaults to the repository root.",
    )
    parser.add_argument(
        "--required",
        action="append",
        default=[],
        help="Relative JSON path that must exist. Can be repeated.",
    )
    parser.add_argument(
        "--max-running-minutes",
        type=int,
        default=240,
        help="Warn if a daemon status is running longer than this threshold.",
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Do not write reports/openclaw-runtime-validation-latest.*.",
    )
    args = parser.parse_args()

    root = Path(args.project_root)
    required = set(args.required or [])
    ok = True
    files: list[dict[str, Any]] = []
    for rel in DEFAULT_RELATIVE_PATHS:
        passed, item = validate_path(root / rel, required=rel in required)
        print(item["message"])
        files.append(item)
        ok = ok and passed
    issues: list[dict[str, Any]] = []
    backtest = analyze_backtest(root, issues)
    dynamic_universe = analyze_dynamic_universe(root, issues)
    daemons = analyze_daemons(root, issues, args.max_running_minutes)
    if any(issue["severity"] == "critical" for issue in issues):
        ok = False
    payload = {
        "generated_at": utc_now(),
        "status": "ok" if ok else "failed",
        "files": files,
        "issues": issues,
        "backtest": backtest,
        "dynamic_universe": dynamic_universe,
        "daemons": daemons,
    }
    if not args.no_report:
        atomic_write_json(root / DEFAULT_REPORT_JSON, payload)
        atomic_write_text(root / DEFAULT_REPORT_MD, render_markdown(payload))
    for issue in issues:
        print(f"{issue['severity']}: {issue['title']} - {issue['detail']}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
