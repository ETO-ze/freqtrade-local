from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import paramiko


ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"
SETTINGS_PATH = ROOT / "server.openclaw-sync.local.json"
JSON_REPORT = REPORTS / "openclaw-server-status-latest.json"
MD_REPORT = REPORTS / "openclaw-server-status-latest.md"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def run_remote(client: paramiko.SSHClient, command: str, timeout: int = 30) -> str:
    _, stdout, stderr = client.exec_command(command, timeout=timeout)
    out = stdout.read().decode("utf-8", "ignore").strip()
    err = stderr.read().decode("utf-8", "ignore").strip()
    return out or err


def main() -> int:
    settings = load_json(SETTINGS_PATH)
    host = str(settings["host"])
    port = int(settings.get("port") or 22)
    username = str(settings["username"])
    password = str(settings["password"])
    remote_dir = str(settings.get("remote_dir") or "/root/freqtrade-local")
    bot_name = str(settings.get("bot_container_name") or "freqtrade-openclaw-auto")
    remote_api_url = str(settings.get("remote_api_url") or "http://127.0.0.1:8081/api/v1/ping")

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
    finally:
        client.close()

    local_config_path = ROOT / "user_data" / "config.openclaw-auto.json"
    local_config = load_json(local_config_path) if local_config_path.exists() else {}
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
        "restart": {"action": "skipped", "reason": "readonly probe"},
        "uploaded_files": [],
    }

    REPORTS.mkdir(parents=True, exist_ok=True)
    JSON_REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
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
        f"- Selected pairs: {', '.join(selected_pairs) if selected_pairs else 'none'}",
    ]
    MD_REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report: {JSON_REPORT}")
    return 0 if validation_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
