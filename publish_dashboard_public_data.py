import json
import posixpath
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import paramiko


PROJECT_ROOT = Path(__file__).resolve().parent
REPORTS_ROOT = PROJECT_ROOT / "reports"
DAEMON_ROOT = REPORTS_ROOT / "daemon"
SETTINGS_PATH = PROJECT_ROOT / "server.openclaw-sync.local.json"
REMOTE_PUBLIC_ROOT = "/www/wwwroot/duskrain.cn/dashboard-data"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def parse_decision(markdown: str) -> str:
    match = re.search(r"- Decision:\s*(.+)", markdown)
    return match.group(1).strip() if match else ""


def parse_thresholds(markdown: str) -> str:
    match = re.search(r"- Thresholds:\s*(.+)", markdown)
    return match.group(1).strip() if match else ""


def build_backtest_payload() -> dict[str, Any]:
    backtest = load_json(REPORTS_ROOT / "openclaw-auto-backtest-latest.json")
    model = load_json(REPORTS_ROOT / "openclaw-best-model-latest.json")
    daily = load_json(REPORTS_ROOT / "openclaw-daily-alt-ml-stable.json")
    sync_pairs = load_json(REPORTS_ROOT / "openclaw-freqtrade-sync-latest.json")
    feedback = load_json(REPORTS_ROOT / "openclaw-trade-feedback-policy-candidate.json")
    approval_md = read_text(REPORTS_ROOT / "openclaw-auto-approval-latest.md")

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

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "strategy": backtest.get("strategy") or "",
        "timerange": backtest.get("timerange") or "",
        "latest_backtest": backtest.get("latest_backtest") or "",
        "metrics": backtest.get("metrics") or {},
        "selected_pairs": list(sync_pairs.get("selected_pairs") or []),
        "best_model": {
            "model": model.get("selected_model") or "",
            "weight": model.get("model_weight"),
        },
        "top_factors": list((model.get("top_factors") or [])[:8]),
        "timings": list(daily.get("timings") or []),
        "feedback_leaders": feedback_pairs[:6],
        "approval": {
            "decision": parse_decision(approval_md),
            "thresholds": parse_thresholds(approval_md),
        },
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


def upload_payloads(settings: dict[str, Any], payloads: dict[str, dict[str, Any]]) -> None:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=str(settings["host"]),
        port=int(settings.get("port") or 22),
        username=str(settings["username"]),
        password=str(settings["password"]),
        timeout=30,
    )
    sftp = client.open_sftp()
    try:
        ensure_remote_dir(sftp, REMOTE_PUBLIC_ROOT)
        for name, payload in payloads.items():
            remote_path = posixpath.join(REMOTE_PUBLIC_ROOT, f"{name}.json")
            with sftp.open(remote_path, "w") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False, indent=2))
    finally:
        sftp.close()
        client.close()


def main() -> int:
    settings = load_json(SETTINGS_PATH)
    backtest_payload = build_backtest_payload()
    alerts_payload = build_alerts_payload()
    upload_payloads(settings, {"backtest": backtest_payload, "alerts": alerts_payload})
    print("Published dashboard public data: backtest.json, alerts.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
