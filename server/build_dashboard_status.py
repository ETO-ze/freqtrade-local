import json
import subprocess
import base64
import urllib.error
import urllib.request
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


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, "", "N/A", "n/a"):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def first_present(mapping: dict[str, Any], keys: list[str], default: Any = None) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return value
    return default


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def api_auth_token(api_server: dict[str, Any]) -> tuple[str, str | None]:
    username = str(api_server.get("username") or "")
    password = str(api_server.get("password") or "")
    if not username or not password:
        return "", "api credentials missing"
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return token, None


def read_api_json(api_server: dict[str, Any], path: str) -> tuple[Any, str | None]:
    token, error = api_auth_token(api_server)
    if error:
        return None, error
    request = urllib.request.Request(
        f"http://127.0.0.1:8081{path}",
        headers={"Authorization": f"Basic {token}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8", "ignore")
        return json.loads(body or "{}"), None
    except Exception as exc:
        return None, str(exc)


def normalize_ratio(value: Any) -> float:
    numeric = safe_float(value)
    if abs(numeric) > 2:
        return numeric / 100.0
    return numeric


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
    live_trading = read_live_trading(api_server)

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
            "live_trading": live_trading,
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


def read_live_trading(api_server: dict[str, Any]) -> dict[str, Any]:
    payload, status_error = read_api_json(api_server, "/api/v1/status")
    profit_payload, profit_error = read_api_json(api_server, "/api/v1/profit")
    if status_error:
        return {"open_trade_count": None, "open_trade_pairs": [], "error": status_error}

    if isinstance(payload, list):
        trades = payload
    elif isinstance(payload, dict):
        trades = payload.get("trades") or payload.get("data") or payload.get("result") or []
    else:
        trades = []

    open_trades = []
    for trade in trades:
        if not isinstance(trade, dict):
            continue
        if trade.get("is_open") is False:
            continue
        profit_abs = first_present(
            trade,
            ["profit_abs", "current_profit_abs", "realized_profit", "profit_abs_open"],
            0.0,
        )
        profit_ratio = first_present(
            trade,
            ["profit_ratio", "current_profit", "current_profit_ratio", "profit_pct", "profit_ratio_open"],
            0.0,
        )
        profit_ratio = normalize_ratio(profit_ratio)
        open_trades.append(
            {
                "pair": str(trade.get("pair") or ""),
                "trade_id": first_present(trade, ["trade_id", "id"], ""),
                "profit_abs": round(safe_float(profit_abs), 8),
                "profit_ratio": round(profit_ratio, 8),
                "is_short": bool(trade.get("is_short")),
                "open_date": str(first_present(trade, ["open_date", "open_timestamp"], "")),
                "stake_amount": first_present(trade, ["stake_amount", "stake_amount_filled"], None),
                "amount": first_present(trade, ["amount", "amount_requested"], None),
                "open_rate": first_present(trade, ["open_rate", "open_rate_requested"], None),
                "current_rate": first_present(trade, ["current_rate", "close_rate_requested"], None),
                "leverage": first_present(trade, ["leverage"], None),
            }
        )

    cumulative_profit_abs = None
    cumulative_profit_ratio = None
    closed_profit_abs = None
    closed_profit_ratio = None
    closed_trade_count = None
    profit_currency = ""
    if isinstance(profit_payload, dict):
        cumulative_profit_abs = safe_float(
            first_present(profit_payload, ["profit_all_coin", "profit_all_fiat"], None)
        )
        cumulative_profit_ratio = normalize_ratio(
            first_present(profit_payload, ["profit_all_ratio", "profit_all_percent"], None)
        )
        closed_profit_abs = safe_float(
            first_present(profit_payload, ["profit_closed_coin", "profit_closed_fiat"], None)
        )
        closed_profit_ratio = normalize_ratio(
            first_present(profit_payload, ["profit_closed_ratio", "profit_closed_percent"], None)
        )
        closed_trade_count = int(safe_float(profit_payload.get("closed_trade_count"), 0))
        profit_currency = str(first_present(profit_payload, ["stake_currency", "fiat_currency"], ""))

    return {
        "synced_at": utc_now(),
        "open_trade_count": len(open_trades),
        "open_trade_pairs": [item["pair"] for item in open_trades if item.get("pair")],
        "total_profit_abs": round(sum(safe_float(item.get("profit_abs")) for item in open_trades), 6),
        "total_profit_ratio": round(sum(safe_float(item.get("profit_ratio")) for item in open_trades), 6),
        "cumulative_profit_abs": round(cumulative_profit_abs, 8) if cumulative_profit_abs is not None else None,
        "cumulative_profit_ratio": round(cumulative_profit_ratio, 8) if cumulative_profit_ratio is not None else None,
        "closed_profit_abs": round(closed_profit_abs, 8) if closed_profit_abs is not None else None,
        "closed_profit_ratio": round(closed_profit_ratio, 8) if closed_profit_ratio is not None else None,
        "closed_trade_count": closed_trade_count,
        "profit_currency": profit_currency,
        "profit_error": profit_error,
        "trades": open_trades[:12],
    }


def main() -> int:
    PUBLIC_ROOT.mkdir(parents=True, exist_ok=True)
    payload = build_status()
    PUBLIC_STATUS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {PUBLIC_STATUS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

