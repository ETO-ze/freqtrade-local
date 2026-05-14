from __future__ import annotations

import base64
import json
import sys
import time
from pathlib import Path
from typing import Any

import paramiko


ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports"
SETTINGS_PATH = ROOT / "server.openclaw-sync.local.json"
JSON_REPORT = REPORTS / "openclaw-server-status-latest.json"
MD_REPORT = REPORTS / "openclaw-server-status-latest.md"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


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


def run_remote(client: paramiko.SSHClient, command: str, timeout: int = 30) -> str:
    _, stdout, stderr = client.exec_command(command, timeout=timeout)
    out = stdout.read().decode("utf-8", "ignore").strip()
    err = stderr.read().decode("utf-8", "ignore").strip()
    return out or err


def api_status_url(remote_api_url: str) -> str:
    if remote_api_url.endswith("/ping"):
        return remote_api_url[: -len("/ping")] + "/status"
    if remote_api_url.endswith("/api/v1"):
        return remote_api_url + "/status"
    return remote_api_url.rstrip("/") + "/status"


def load_api_auth(local_config: dict[str, Any]) -> tuple[str, str]:
    api_server = local_config.get("api_server") or {}
    username = str(api_server.get("username") or "")
    password = str(api_server.get("password") or "")
    return username, password


def check_open_trades(client: paramiko.SSHClient, remote_api_url: str, local_config: dict[str, Any]) -> dict[str, Any]:
    username, password = load_api_auth(local_config)
    if not username or not password:
        return {"ok": False, "reason": "api credentials missing", "open_trade_count": None, "open_trades": []}

    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    url = api_status_url(remote_api_url)
    script = f"""
import json
import urllib.request

url = {url!r}
headers = {{"Authorization": "Basic {token}", "Accept": "application/json"}}
try:
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=10) as response:
        body = response.read().decode("utf-8", "ignore")
    payload = json.loads(body or "[]")
    if isinstance(payload, list):
        trades = payload
    elif isinstance(payload, dict):
        trades = payload.get("trades") or payload.get("data") or payload.get("result") or []
    else:
        trades = []
    open_trades = []
    total_profit_abs = 0.0
    for trade in trades:
        if not isinstance(trade, dict):
            continue
        if trade.get("is_open") is False:
            continue
        pair = str(trade.get("pair") or "")
        profit_abs = float(trade.get("profit_abs") or trade.get("profit_abs_open") or 0.0)
        profit_ratio = float(trade.get("profit_ratio") or trade.get("profit_ratio_open") or 0.0)
        total_profit_abs += profit_abs
        open_trades.append({{
            "pair": pair,
            "direction": "short" if trade.get("is_short") else "long",
            "leverage": trade.get("leverage"),
            "profit_abs": round(profit_abs, 8),
            "profit_pct": round(profit_ratio * 100, 4),
            "open_date": trade.get("open_date") or trade.get("open_date_utc") or trade.get("open_date_hum") or "",
        }})
    print(json.dumps({{
        "ok": True,
        "status_url": url,
        "open_trade_count": len(open_trades),
        "open_trade_pairs": [item["pair"] for item in open_trades if item.get("pair")],
        "open_trades": open_trades[:20],
        "total_open_profit_abs": round(total_profit_abs, 8),
    }}, ensure_ascii=False))
except Exception as exc:
    print(json.dumps({{
        "ok": False,
        "status_url": url,
        "reason": str(exc),
        "open_trade_count": None,
        "open_trades": [],
    }}, ensure_ascii=False))
"""
    text = run_remote(client, f"python3 - <<'PY'\n{script}\nPY", timeout=30)
    try:
        return json.loads(text.splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return {"ok": False, "reason": text, "open_trade_count": None, "open_trades": []}


def main() -> int:
    settings = load_json(SETTINGS_PATH)
    host = str(settings["host"])
    port = int(settings.get("port") or 22)
    username = str(settings["username"])
    password = str(settings["password"])
    remote_dir = str(settings.get("remote_dir") or "/root/freqtrade-local")
    bot_name = str(settings.get("bot_container_name") or "freqtrade-openclaw-auto")
    remote_api_url = str(settings.get("remote_api_url") or "http://127.0.0.1:8081/api/v1/ping")
    local_config_path = ROOT / "user_data" / "config.openclaw-auto.json"
    local_config = load_json(local_config_path) if local_config_path.exists() else {}

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, port=port, username=username, password=password, timeout=30, banner_timeout=30, auth_timeout=30)
    try:
        remote_status = {
            "hostname": run_remote(client, "hostname"),
            "docker_ps": run_remote(client, "docker ps --format 'table {{.Names}}\\t{{.Status}}\\t{{.Ports}}'", timeout=30),
            "openclaw_processes": run_remote(
                client,
                "ps -ef | grep -Ei 'freqtrade-factor-daemon|freqtrade-daily-ml-screen|freqtrade-auto-tune-alternativehunter|freqtrade-trade-feedback-isolated|freqtrade-backtest-openclaw-auto' | grep -v grep || true",
                timeout=30,
            ),
            "bot_running": run_remote(client, f"docker inspect -f '{{{{.State.Running}}}}' {bot_name} 2>/dev/null || true"),
            "bot_status": run_remote(client, f"docker inspect -f '{{{{.State.Status}}}}' {bot_name} 2>/dev/null || true"),
            "api_ping": run_remote(client, f"curl -s {remote_api_url} || true"),
            "api_http_code": run_remote(client, f"curl -s -o /tmp/openclaw_probe_ping.out -w '%{{http_code}}' {remote_api_url} || true"),
        }
        open_trade_check = check_open_trades(client, remote_api_url, local_config)
    finally:
        client.close()

    selected_pairs = list((local_config.get("exchange") or {}).get("pair_whitelist") or [])
    generated_at = time.strftime("%Y-%m-%d %H:%M:%S")
    validation_ok = str(remote_status.get("api_http_code") or "") == "200"

    payload: dict[str, Any] = {
        "generated_at": generated_at,
        "mode": "probe-readonly",
        "source": {
            "config_path": str(local_config_path),
            "selected_pairs": selected_pairs,
        },
        "remote": {
            "host": host,
            "port": port,
            "remote_dir": remote_dir,
            "bot_container_name": bot_name,
            "remote_api_url": remote_api_url,
        },
        "remote_status_before": remote_status,
        "remote_status_after": remote_status,
        "validation": {
            "ok": validation_ok,
            "http_code": int(remote_status["api_http_code"]) if str(remote_status.get("api_http_code") or "").isdigit() else 0,
            "body": remote_status.get("api_ping") or "",
        },
        "open_trade_check": open_trade_check,
        "restart": {"action": "skipped", "reason": "readonly probe"},
        "uploaded_files": [],
    }

    atomic_write_json(JSON_REPORT, payload)
    lines = [
        "# OpenClaw Server Status",
        "",
        f"- Generated: {generated_at}",
        "- Mode: probe-readonly",
        f"- Remote host: {host}",
        f"- Remote dir: {remote_dir}",
        f"- Bot running: {remote_status.get('bot_running')}",
        f"- Bot status: {remote_status.get('bot_status')}",
        f"- API healthy: {validation_ok}",
        f"- HTTP code: {payload['validation']['http_code']}",
        f"- Open trade check: {open_trade_check.get('ok')}",
        f"- Open trades: {open_trade_check.get('open_trade_count')}",
        f"- Open profit: {open_trade_check.get('total_open_profit_abs', 'n/a')}",
        f"- Selected pairs: {', '.join(selected_pairs) if selected_pairs else 'none'}",
    ]
    atomic_write_text(MD_REPORT, "\n".join(lines))
    print(f"Report: {JSON_REPORT}")
    return 0 if validation_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

