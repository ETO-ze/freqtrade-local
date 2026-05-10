import json
import posixpath
import re
import time
import zipfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import paramiko


PROJECT_ROOT = Path(__file__).resolve().parent
REPORTS_ROOT = PROJECT_ROOT / "reports"
DAEMON_ROOT = REPORTS_ROOT / "daemon"
SETTINGS_PATH = PROJECT_ROOT / "server.openclaw-sync.local.json"
REMOTE_PUBLIC_ROOT = "/www/wwwroot/duskrain.cn/dashboard-data"
LOCAL_PUBLIC_ROOT = PROJECT_ROOT / "dashboard-data"
MANUAL_PROMOTION_REPORT = REPORTS_ROOT / "openclaw-manual-promotion-latest.md"
BACKTEST_RESULT_ROOT = PROJECT_ROOT / "user_data" / "backtest_results"
PROJECT_ROADMAP_PATH = PROJECT_ROOT / "PROJECT_ROADMAP.json"


def load_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return default or {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default or {}


def read_text(path: Path, default: str = "") -> str:
    if not path.exists():
        return default
    return path.read_text(encoding="utf-8-sig")


def parse_decision(markdown: str) -> str:
    match = re.search(r"- Decision:\s*(.+)", markdown)
    return match.group(1).strip() if match else ""


def parse_thresholds(markdown: str) -> str:
    match = re.search(r"- Thresholds:\s*(.+)", markdown)
    return match.group(1).strip() if match else ""


def as_history_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        nested = value.get("value")
        if isinstance(nested, list):
            return [item for item in nested if isinstance(item, dict)]
        return [value]
    return []


def metrics_from_approved_factor(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "total_profit_pct": item.get("total_profit_pct"),
        "total_profit_usdt": item.get("total_profit_usdt"),
        "profit_factor": item.get("profit_factor"),
        "winrate": item.get("winrate") or item.get("winrate_pct"),
        "max_drawdown_pct": item.get("max_drawdown_pct"),
        "max_drawdown_abs": item.get("max_drawdown_abs"),
        "trade_count": item.get("trade_count"),
        "final_balance": item.get("final_balance"),
        "sharpe": item.get("sharpe"),
        "sortino": item.get("sortino"),
        "calmar": item.get("calmar"),
        "sqn": item.get("sqn"),
    }


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, "", "N/A", "n/a"):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def resolve_backtest_zip(backtest: dict[str, Any]) -> Path | None:
    latest = str(backtest.get("latest_backtest") or "")
    candidates: list[Path] = []
    if latest:
        latest_path = Path(latest)
        candidates.append(latest_path if latest_path.is_absolute() else BACKTEST_RESULT_ROOT / latest_path)
    if BACKTEST_RESULT_ROOT.exists():
        candidates.extend(sorted(BACKTEST_RESULT_ROOT.glob("*.zip"), key=lambda path: path.stat().st_mtime, reverse=True))
    for path in candidates:
        if path.exists() and path.suffix.lower() == ".zip":
            return path
    return None


def read_backtest_strategy(zip_path: Path) -> tuple[str, dict[str, Any]]:
    with zipfile.ZipFile(zip_path) as archive:
        result_names = [
            name
            for name in archive.namelist()
            if name.endswith(".json") and not name.endswith("_config.json")
        ]
        if not result_names:
            return "", {}
        payload = json.loads(archive.read(result_names[0]).decode("utf-8"))
    strategies = payload.get("strategy") or {}
    if not strategies:
        return "", {}
    name, strategy = next(iter(strategies.items()))
    return str(name), strategy if isinstance(strategy, dict) else {}


def build_backtest_detail_payload(backtest: dict[str, Any]) -> dict[str, Any]:
    zip_path = resolve_backtest_zip(backtest)
    if not zip_path:
        return {}
    try:
        strategy_name, strategy = read_backtest_strategy(zip_path)
    except Exception as exc:
        return {"source_zip": str(zip_path), "error": str(exc)}
    if not strategy:
        return {"source_zip": str(zip_path), "error": "strategy result missing"}

    starting_balance = safe_float(strategy.get("starting_balance"))
    equity_curve: list[dict[str, Any]] = []
    equity = starting_balance
    peak = starting_balance
    for item in strategy.get("daily_profit") or []:
        if not isinstance(item, list) or len(item) < 2:
            continue
        profit_abs = safe_float(item[1])
        equity += profit_abs
        peak = max(peak, equity)
        drawdown_pct = ((equity - peak) / peak * 100) if peak else 0
        equity_curve.append(
            {
                "date": item[0],
                "profit_abs": round(profit_abs, 6),
                "equity": round(equity, 6),
                "drawdown_pct": round(drawdown_pct, 4),
            }
        )

    trades = [item for item in (strategy.get("trades") or []) if isinstance(item, dict)]
    side_groups: dict[str, list[dict[str, Any]]] = {"long": [], "short": []}
    pair_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        side = "short" if trade.get("is_short") else "long"
        side_groups[side].append(trade)
        pair_groups[str(trade.get("pair") or "unknown")].append(trade)

    def summarize_trades(items: list[dict[str, Any]]) -> dict[str, Any]:
        count = len(items)
        wins = sum(1 for item in items if safe_float(item.get("profit_abs")) > 0)
        losses = sum(1 for item in items if safe_float(item.get("profit_abs")) < 0)
        profit_abs = sum(safe_float(item.get("profit_abs")) for item in items)
        avg_profit_pct = sum(safe_float(item.get("profit_ratio")) for item in items) / count * 100 if count else 0
        avg_leverage = sum(safe_float(item.get("leverage")) for item in items) / count if count else 0
        return {
            "trades": count,
            "wins": wins,
            "losses": losses,
            "winrate": round(wins / count * 100, 2) if count else 0,
            "profit_abs": round(profit_abs, 6),
            "avg_profit_pct": round(avg_profit_pct, 4),
            "avg_leverage": round(avg_leverage, 4),
        }

    side_stats = [{"side": side, **summarize_trades(items)} for side, items in side_groups.items()]
    pair_trade_stats = [
        {
            "pair": pair,
            **summarize_trades(items),
            "long_trades": sum(1 for item in items if not item.get("is_short")),
            "short_trades": sum(1 for item in items if item.get("is_short")),
        }
        for pair, items in pair_groups.items()
    ]
    pair_trade_stats.sort(key=lambda item: safe_float(item.get("profit_abs")), reverse=True)

    pair_ranking = []
    for item in strategy.get("results_per_pair") or []:
        if not isinstance(item, dict) or item.get("key") == "TOTAL":
            continue
        pair_ranking.append(
            {
                "pair": item.get("key"),
                "trades": item.get("trades"),
                "profit_total_pct": item.get("profit_total_pct"),
                "profit_total_abs": item.get("profit_total_abs"),
                "winrate": round(safe_float(item.get("winrate")) * 100, 2),
                "profit_factor": item.get("profit_factor"),
                "max_drawdown_abs": item.get("max_drawdown_abs"),
            }
        )
    pair_ranking.sort(key=lambda item: safe_float(item.get("profit_total_abs")), reverse=True)

    monthly = []
    for item in ((strategy.get("periodic_breakdown") or {}).get("month") or []):
        if not isinstance(item, dict):
            continue
        date_ts = safe_float(item.get("date_ts"))
        date = datetime.fromtimestamp(date_ts / 1000) if date_ts else None
        profit_abs = safe_float(item.get("profit_abs"))
        monthly.append(
            {
                "date": item.get("date"),
                "year": date.year if date else None,
                "month": date.month if date else None,
                "profit_abs": round(profit_abs, 6),
                "profit_pct": round(profit_abs / starting_balance * 100, 4) if starting_balance else 0,
                "trades": item.get("trades"),
                "wins": item.get("wins"),
                "losses": item.get("losses"),
                "profit_factor": item.get("profit_factor"),
            }
        )

    return {
        "source_zip": zip_path.name,
        "strategy_name": strategy_name,
        "starting_balance": starting_balance,
        "final_balance": strategy.get("final_balance"),
        "max_drawdown_pct": round(safe_float(strategy.get("max_drawdown_account")) * 100, 4),
        "trade_count_long": strategy.get("trade_count_long"),
        "trade_count_short": strategy.get("trade_count_short"),
        "equity_curve": equity_curve,
        "pair_ranking": pair_ranking,
        "side_stats": side_stats,
        "monthly": monthly,
        "pair_trade_stats": pair_trade_stats,
    }


def build_live_trading_payload(server_sync: dict[str, Any], server_status: dict[str, Any]) -> dict[str, Any]:
    status = server_sync.get("remote_status_after") or server_sync.get("remote_status_before") or server_status.get("remote_status_after") or server_status.get("remote_status_before") or {}
    restart = server_sync.get("restart") or {}
    protection = restart.get("open_trade_protection") or {}
    check = protection.get("check") or {}
    validation = server_sync.get("validation") or server_status.get("validation") or {}
    return {
        "generated_at": server_sync.get("generated_at") or server_status.get("generated_at") or "",
        "mode": server_sync.get("mode") or server_status.get("mode") or "",
        "bot_running": status.get("bot_running"),
        "bot_status": status.get("bot_status"),
        "api_ok": validation.get("ok"),
        "api_http_code": validation.get("http_code") or status.get("api_http_code"),
        "restart_action": restart.get("action"),
        "restart_reason": restart.get("reason"),
        "open_trade_count": check.get("open_trade_count"),
        "open_trade_pairs": list(check.get("pairs") or []),
    }


def select_active_factor(
    approved_history: list[dict[str, Any]],
    runtime_policy: dict[str, Any],
    active_config: dict[str, Any],
) -> dict[str, Any]:
    active_factor = runtime_policy.get("active_approved_factor")
    if isinstance(active_factor, dict) and active_factor:
        return active_factor

    if not approved_history:
        return {}

    manual_report = read_text(MANUAL_PROMOTION_REPORT)
    approved_at_match = re.search(r"- Source approved at:\s*(.+)", manual_report)
    backtest_match = re.search(r"- Backtest:\s*(.+)", manual_report)
    approved_at = approved_at_match.group(1).strip() if approved_at_match else ""
    backtest_name = backtest_match.group(1).strip() if backtest_match else ""
    if approved_at or backtest_name:
        for item in approved_history:
            if approved_at and str(item.get("generated_at") or "") == approved_at:
                return item
            if backtest_name and str(item.get("latest_backtest") or "") == backtest_name:
                return item

    return max(approved_history, key=lambda item: float(item.get("total_profit_pct") or 0))


def manual_active_pairs() -> list[str]:
    manual_report = read_text(MANUAL_PROMOTION_REPORT)
    match = re.search(r"- Active pairs:\s*(.+)", manual_report)
    if not match:
        return []
    return [item.strip() for item in match.group(1).split(",") if item.strip()]


def build_backtest_payload() -> dict[str, Any]:
    backtest = load_json(REPORTS_ROOT / "openclaw-auto-backtest-latest.json")
    model = load_json(REPORTS_ROOT / "openclaw-best-model-latest.json")
    daily = load_json(REPORTS_ROOT / "openclaw-daily-alt-ml-stable.json")
    sync_pairs = load_json(REPORTS_ROOT / "openclaw-freqtrade-sync-latest.json")
    server_sync = load_json(REPORTS_ROOT / "openclaw-server-sync-latest.json")
    server_status = load_json(REPORTS_ROOT / "openclaw-server-status-latest.json")
    feedback = load_json(REPORTS_ROOT / "openclaw-trade-feedback-policy-candidate.json")
    approval_md = read_text(REPORTS_ROOT / "openclaw-auto-approval-latest.md")
    approved_history = as_history_list(load_json(REPORTS_ROOT / "openclaw-approved-history.json", default=[]))
    runtime_policy = load_json(PROJECT_ROOT / "user_data" / "model_runtime_policy.json")
    project_roadmap = load_json(PROJECT_ROADMAP_PATH, default={"items": []})
    active_config = load_json(PROJECT_ROOT / "user_data" / "config.openclaw-auto.json")
    active_factor = select_active_factor(approved_history, runtime_policy, active_config)
    active_pairs = manual_active_pairs() or list((active_config.get("exchange") or {}).get("pair_whitelist") or [])
    active_metrics = metrics_from_approved_factor(active_factor) if active_factor else {}

    feedback_pairs: list[dict[str, Any]] = []
    for pair, item in (feedback.get("pairs") or {}).items():
        feedback_pairs.append(
            {
                "pair": pair,
                "feedback_score": item.get("feedback_score"),
                "trades": item.get("trades"),
                "winrate": item.get("winrate"),
                "profit_factor": item.get("profit_factor"),
                "suggested_action": item.get("suggested_action"),
            }
        )
    feedback_pairs.sort(key=lambda item: float(item.get("feedback_score") or 0), reverse=True)

    latest_candidate = {
        "generated_at": backtest.get("generated_at") or "",
        "strategy": backtest.get("strategy") or "",
        "timerange": backtest.get("timerange") or "",
        "latest_backtest": backtest.get("latest_backtest") or "",
        "metrics": backtest.get("metrics") or {},
        "approval": {
            "decision": parse_decision(approval_md),
            "thresholds": parse_thresholds(approval_md),
        },
    }

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "display_mode": "active_approved_factor",
        "strategy": active_factor.get("strategy") or active_config.get("strategy") or backtest.get("strategy") or "",
        "timerange": active_factor.get("timerange") or backtest.get("timerange") or "",
        "latest_backtest": active_factor.get("latest_backtest") or "",
        "metrics": active_metrics or backtest.get("metrics") or {},
        "selected_pairs": active_pairs or list(active_factor.get("selected_pairs") or []) or list(sync_pairs.get("selected_pairs") or []),
        "active_factor": {
            "generated_at": active_factor.get("generated_at") or "",
            "strategy": active_factor.get("strategy") or active_config.get("strategy") or "",
            "best_model": active_factor.get("best_model") or active_factor.get("model") or "",
            "approval_mode": active_factor.get("approval_mode") or "",
            "latest_backtest": active_factor.get("latest_backtest") or "",
            "selected_pairs": active_pairs or list(active_factor.get("selected_pairs") or []),
            "metrics": active_metrics,
            "top_factors": list((active_factor.get("top_factors") or [])[:8]),
            "source": "runtime_policy" if runtime_policy.get("active_approved_factor") else "approved_history_match",
        },
        "latest_candidate": latest_candidate,
        "best_model": {
            "model": active_factor.get("best_model") or active_factor.get("model") or model.get("selected_model") or "",
            "weight": model.get("model_weight"),
        },
        "top_factors": list((active_factor.get("top_factors") or model.get("top_factors") or [])[:8]),
        "timings": list(daily.get("timings") or []),
        "feedback_leaders": feedback_pairs[:6],
        "approval": {
            "decision": "active approved factor in use" if active_factor else parse_decision(approval_md),
            "thresholds": parse_thresholds(approval_md),
        },
        "backtest_detail": build_backtest_detail_payload(backtest),
        "live_trading": build_live_trading_payload(server_sync, server_status),
        "project_roadmap": project_roadmap,
        "approved_history": approved_history,
    }


def severity_rank(value: str) -> int:
    return {"critical": 0, "warning": 1, "info": 2}.get(value, 3)


def build_alerts_payload() -> dict[str, Any]:
    stable = load_json(DAEMON_ROOT / "factor-daemon-stable-status.json")
    fast = load_json(DAEMON_ROOT / "factor-daemon-fast-status.json")
    evolution = load_json(DAEMON_ROOT / "factor-daemon-evolution-status.json")
    autotune = load_json(DAEMON_ROOT / "factor-daemon-autotune-status.json")
    server_sync = load_json(REPORTS_ROOT / "openclaw-server-sync-latest.json")
    approval_md = read_text(REPORTS_ROOT / "openclaw-auto-approval-latest.md")
    backtest = load_json(REPORTS_ROOT / "openclaw-auto-backtest-latest.json")

    alerts: list[dict[str, Any]] = []

    def add_alert(severity: str, source: str, title: str, detail: str, occurred_at: str) -> None:
        alerts.append(
            {
                "severity": severity,
                "source": source,
                "title": title,
                "detail": detail,
                "occurred_at": occurred_at,
            }
        )

    def daemon_alert(source: str, payload: dict[str, Any]) -> None:
        status = str(payload.get("status") or "")
        error = str(payload.get("error") or "")
        occurred_at = str(payload.get("completed_at") or payload.get("started_at") or "")
        if status == "ok":
            return
        if "Stopped by user." in error:
            add_alert("info", source, f"{source} stopped by user", error, occurred_at)
            return
        if "shared workflow lock" in error:
            add_alert("warning", source, f"{source} skipped by shared lock", error, occurred_at)
            return
        if status == "skipped":
            add_alert("warning", source, f"{source} skipped", error or "workflow skipped", occurred_at)
            return
        if error:
            add_alert("critical", source, f"{source} runtime issue", error, occurred_at)

    daemon_alert("stable", stable)
    daemon_alert("fast", fast)
    daemon_alert("evolution", evolution)
    daemon_alert("autotune", autotune)

    decision = parse_decision(approval_md)
    thresholds = parse_thresholds(approval_md)
    metrics = backtest.get("metrics") or {}
    if "rejected" in decision.lower():
        add_alert(
            "warning",
            "approval",
            "promotion gate blocked candidate",
            f"{decision} Profit {metrics.get('total_profit_pct')}%, PF {metrics.get('profit_factor')}, Trades {metrics.get('trade_count')}. Thresholds: {thresholds}",
            str(backtest.get("generated_at") or ""),
        )

    validation = (server_sync.get("validation") or {})
    if validation.get("ok"):
        add_alert(
            "info",
            "server-sync",
            "server sync validation passed",
            f"Remote API returned HTTP {validation.get('http_code')}.",
            str(server_sync.get("generated_at") or ""),
        )
    else:
        add_alert(
            "critical",
            "server-sync",
            "server sync validation failed",
            f"Remote API validation failed with HTTP {validation.get('http_code')}.",
            str(server_sync.get("generated_at") or ""),
        )

    alerts.sort(key=lambda item: (severity_rank(item["severity"]), item["occurred_at"]))

    counts = {"critical": 0, "warning": 0, "info": 0}
    for item in alerts:
        counts[item["severity"]] = counts.get(item["severity"], 0) + 1

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "counts": counts,
        "alerts": alerts[:12],
    }


def ensure_remote_dir(sftp: paramiko.SFTPClient, remote_dir: str) -> None:
    parts: list[str] = []
    path = remote_dir
    while path not in ("", "/"):
        parts.append(path)
        path = posixpath.dirname(path)
    for part in reversed(parts):
        try:
            sftp.stat(part)
        except OSError:
            sftp.mkdir(part)


def quote_single(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def connect_ssh(settings: dict[str, Any], attempts: int = 4, delay_seconds: int = 8) -> paramiko.SSHClient:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                hostname=str(settings["host"]),
                port=int(settings.get("port") or 22),
                username=str(settings["username"]),
                password=str(settings["password"]),
                timeout=90,
                banner_timeout=90,
                auth_timeout=90,
                look_for_keys=False,
                allow_agent=False,
            )
            return client
        except Exception as exc:
            last_error = exc
            client.close()
            if attempt < attempts:
                print(f"SSH upload connection attempt {attempt} failed: {exc}. Retrying in {delay_seconds}s...")
                time.sleep(delay_seconds)
    raise RuntimeError(f"SSH upload connection failed after {attempts} attempts: {last_error}") from last_error


def run_remote(client: paramiko.SSHClient, command: str, timeout: int = 60) -> None:
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    out = stdout.read().decode("utf-8", "ignore")
    err = stderr.read().decode("utf-8", "ignore")
    code = stdout.channel.recv_exit_status()
    if code != 0:
        raise RuntimeError(f"Remote command failed ({code}): {out}\n{err}")


def run_remote_with_stdin(client: paramiko.SSHClient, command: str, stdin_text: str, timeout: int = 120) -> None:
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    stdin.write(stdin_text)
    stdin.channel.shutdown_write()
    out = stdout.read().decode("utf-8", "ignore")
    err = stderr.read().decode("utf-8", "ignore")
    code = stdout.channel.recv_exit_status()
    if code != 0:
        raise RuntimeError(f"Remote command failed ({code}): {out}\n{err}")


def upload_payloads(settings: dict[str, Any], payloads: dict[str, dict[str, Any]]) -> None:
    client = connect_ssh(settings)
    try:
        upload_bundle = {
            "remote_root": REMOTE_PUBLIC_ROOT,
            "files": {
                f"{name}.json": payload for name, payload in payloads.items()
            },
        }
        remote_script = (
            "python3 -c \"import json, pathlib, sys; "
            "bundle=json.load(sys.stdin); "
            "root=pathlib.Path(bundle['remote_root']); root.mkdir(parents=True, exist_ok=True); "
            "[root.joinpath(name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8') "
            "for name, payload in bundle['files'].items()]\""
        )
        run_remote_with_stdin(
            client,
            remote_script,
            json.dumps(upload_bundle, ensure_ascii=False),
            timeout=120,
        )
    finally:
        client.close()


def write_local_payloads(payloads: dict[str, dict[str, Any]]) -> None:
    LOCAL_PUBLIC_ROOT.mkdir(parents=True, exist_ok=True)
    for name, payload in payloads.items():
        (LOCAL_PUBLIC_ROOT / f"{name}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def main() -> int:
    settings = load_json(SETTINGS_PATH)
    backtest_payload = build_backtest_payload()
    alerts_payload = build_alerts_payload()
    payloads = {"backtest": backtest_payload, "alerts": alerts_payload}
    write_local_payloads(payloads)
    upload_payloads(settings, payloads)
    print("Published dashboard public data: backtest.json, alerts.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
