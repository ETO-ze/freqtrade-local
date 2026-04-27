import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REMOTE_ROOT = Path("/root/freqtrade-local")
PUBLIC_ROOT = Path("/www/wwwroot/duskrain.cn/dashboard-data")
CONFIG_PATH = REMOTE_ROOT / "user_data" / "config.openclaw-auto.json"
SYNC_META_PATH = REMOTE_ROOT / "dashboard-data" / "last-sync.json"
PUBLIC_STATUS_PATH = PUBLIC_ROOT / "status.json"


def run(command: list[str]) -> tuple[int, str]:
    result = subprocess.run(command, capture_output=True, text=True)
    output = (result.stdout or result.stderr or "").strip()
    return result.returncode, output


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_status() -> dict[str, Any]:
    config = load_json(CONFIG_PATH)
    sync_meta = load_json(SYNC_META_PATH)
    exchange = config.get("exchange") or {}
    api_server = config.get("api_server") or {}
    bot_name = str(config.get("bot_name") or "freqtrade-openclaw-auto")
    pair_whitelist = list(exchange.get("pair_whitelist") or [])

    code, docker_state = run(["docker", "inspect", "-f", "{{.State.Status}}", bot_name])
    bot_status = docker_state if code == 0 else "missing"

    code, docker_running = run(["docker", "inspect", "-f", "{{.State.Running}}", bot_name])
    bot_running = docker_running.lower() == "true" if code == 0 else False

    code, started_at = run(["docker", "inspect", "-f", "{{.State.StartedAt}}", bot_name])
    bot_started_at = started_at if code == 0 else ""

    code, ps_status = run(["docker", "ps", "--filter", f"name={bot_name}", "--format", "{{.Status}}"])
    bot_uptime = ps_status if code == 0 else ""

    code, api_ping = run(["curl", "-s", "http://127.0.0.1:8081/api/v1/ping"])
    api_ok = code == 0 and '"pong"' in api_ping

    status = {
        "generated_at": utc_now(),
        "server": {
            "hostname": run(["hostname"])[1],
        },
        "bot": {
            "name": bot_name,
            "status": bot_status,
            "running": bot_running,
            "uptime": bot_uptime,
            "started_at": bot_started_at,
            "strategy": str(config.get("strategy") or ""),
            "timeframe": str(config.get("timeframe") or ""),
            "max_open_trades": int(config.get("max_open_trades") or 0),
            "dry_run": bool(config.get("dry_run")),
            "stake_currency": str(config.get("stake_currency") or ""),
            "stake_amount": config.get("stake_amount"),
            "listen_port": int(api_server.get("listen_port") or 0),
            "pair_count": len(pair_whitelist),
            "tradable_pairs": pair_whitelist,
        },
        "api": {
            "healthy": api_ok,
            "response": api_ping if api_ok else "",
            "checked_at": utc_now(),
        },
        "sync": {
            "last_sync_at": str(sync_meta.get("generated_at") or ""),
            "mode": str(sync_meta.get("mode") or ""),
            "strategy": str(sync_meta.get("strategy") or ""),
            "timeframe": str(sync_meta.get("timeframe") or ""),
            "selected_pair_count": int(sync_meta.get("selected_pair_count") or 0),
            "selected_pairs": list(sync_meta.get("selected_pairs") or []),
            "validation_ok": bool((sync_meta.get("validation") or {}).get("ok")),
            "validation_http_code": int((sync_meta.get("validation") or {}).get("http_code") or 0),
        },
    }
    return status


def main() -> int:
    PUBLIC_ROOT.mkdir(parents=True, exist_ok=True)
    payload = build_status()
    PUBLIC_STATUS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {PUBLIC_STATUS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
