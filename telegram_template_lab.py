from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

import streamlit as st


ROOT = Path(__file__).resolve().parent
REPORT_ROOT = ROOT / "reports"
TEMPLATE_PATH = ROOT / "telegram_message_template.json"
NOTIFICATION_CONFIG_PATH = ROOT / "openclaw.notification.json"
SIM_NOTIFICATION_CONFIG_PATH = ROOT / "openclaw.notification.sim.json"
DAILY_REPORT_PATH = REPORT_ROOT / "openclaw-daily-alt-ml-stable.json"
BEST_MODEL_PATH = REPORT_ROOT / "openclaw-best-model-stable.json"
BACKTEST_PATH = REPORT_ROOT / "openclaw-auto-backtest-stable.json"

DEFAULT_TEMPLATE = (
    "\U0001f4ca OpenClaw \u5c71\u5be8\u65e5\u62a5\n\n"
    "\U0001f552 \u65f6\u95f4: {{generated_at}}\n"
    "\U0001f916 \u6a21\u578b: {{best_model_name}} | {{models_text}}\n"
    "\U0001f4b9 \u5019\u9009\u56de\u6d4b: {{candidate_profit_signed}} | PF {{candidate_profit_factor}} | \u56de\u64a4 {{candidate_drawdown_pct}}% | {{candidate_trades}} \u7b14\n\n"
    "\u2705 \u53ef\u4ea4\u6613:\n"
    "{{tradable_symbols}}\n\n"
    "\U0001f440 \u89c2\u5bdf:\n"
    "{{observe_symbols}}\n\n"
    "\u23f8\ufe0f \u6682\u505c:\n"
    "{{pause_symbols_short}}\n"
    "\u5171 {{pause_count}} \u4e2a"
)

DETAIL_TEMPLATE = (
    "OpenClaw Daily Alt Screen\n"
    "Date: {{generated_at}}\n"
    "Strategy: {{strategy_name}}\n"
    "Models: {{models}}\n"
    "Best model: {{best_model_name}} ({{best_model_weight}})\n"
    "Candidate profit: {{candidate_profit_pct}}%\n"
    "Profit factor: {{candidate_profit_factor}}\n"
    "Max drawdown: {{candidate_drawdown_pct}}%\n"
    "Trades: {{candidate_trades}}\n"
    "Tradable: {{tradable_pairs}}\n"
    "Observe: {{observe_pairs}}\n"
    "Pause: {{pause_pairs}}\n"
    "Report: {{combined_report_path}}"
)


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_template() -> str:
    data = load_json(TEMPLATE_PATH)
    if not data:
        return DEFAULT_TEMPLATE
    return str(data.get("template") or DEFAULT_TEMPLATE)


def mask_value(value: str, keep: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= keep * 2:
        return "*" * len(value)
    return value[:keep] + "*" * (len(value) - keep * 2) + value[-keep:]


def build_context() -> dict[str, str]:
    daily = load_json(DAILY_REPORT_PATH) or {}
    best = load_json(BEST_MODEL_PATH) or {}
    backtest = load_json(BACKTEST_PATH) or {}
    metrics = backtest.get("metrics", {}) if isinstance(backtest, dict) else {}

    tradable_list = [item.get("Pair", "") for item in daily.get("tradable", []) if item.get("Pair")]
    observe_list = [item.get("Pair", "") for item in daily.get("observe", []) if item.get("Pair")]
    pause_list = [item.get("Pair", "") for item in daily.get("pause", []) if item.get("Pair")]

    tradable = ", ".join(tradable_list) or "none"
    observe = ", ".join(observe_list) or "none"
    pause = ", ".join(pause_list) or "none"
    tradable_symbols = ", ".join(pair.split("/")[0] for pair in tradable_list) or "none"
    observe_symbols = ", ".join(pair.split("/")[0] for pair in observe_list) or "none"
    pause_symbols = [pair.split("/")[0] for pair in pause_list]
    pause_symbols_short = ", ".join(pause_symbols[:6]) or "none"
    pause_count = str(len(pause_symbols))
    pause_short = ", ".join(pause_list[:6])
    if len(pause_list) > 6:
        pause_short = f"{pause_short} ... ? {len(pause_list)} ?"
    elif not pause_short:
        pause_short = "none"

    if len(pause_symbols) > 6:
        pause_symbols_short = f"{pause_symbols_short} ..."

    models_value = daily.get("models") or "N/A"
    if isinstance(models_value, list):
        models_text = ", ".join(str(item) for item in models_value)
    else:
        models_text = str(models_value)

    profit_value = metrics.get("total_profit_pct")
    if profit_value in (None, "", "N/A"):
        candidate_profit_signed = "N/A"
    else:
        try:
            profit_float = float(profit_value)
            candidate_profit_signed = f"{profit_float:+.2f}%"
        except (TypeError, ValueError):
            candidate_profit_signed = f"{profit_value}%"

    return {
        "generated_at": str(daily.get("generated_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        "strategy_name": str(daily.get("strategy") or "AlternativeHunter"),
        "models": str(daily.get("models") or "N/A"),
        "models_text": models_text,
        "best_model_name": str(best.get("selected_model") or "N/A"),
        "best_model_weight": str(best.get("model_weight") or "N/A"),
        "candidate_profit_pct": str(metrics.get("total_profit_pct") or "N/A"),
        "candidate_profit_signed": candidate_profit_signed,
        "candidate_profit_factor": str(metrics.get("profit_factor") or "N/A"),
        "candidate_drawdown_pct": str(metrics.get("max_drawdown_pct") or "N/A"),
        "candidate_trades": str(metrics.get("trade_count") or "N/A"),
        "tradable_pairs": tradable,
        "tradable_symbols": tradable_symbols,
        "observe_pairs": observe,
        "observe_symbols": observe_symbols,
        "pause_pairs": pause,
        "pause_pairs_short": pause_short,
        "pause_symbols_short": pause_symbols_short,
        "pause_count": pause_count,
        "combined_report_path": str(REPORT_ROOT / "openclaw-daily-alt-ml-stable.md"),
        "combined_report_name": "openclaw-daily-alt-ml-stable.md",
    }


def render_template(template: str, context: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        return str(context.get(key, f"{{{{{key}}}}}"))

    return re.sub(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}", replace, template)


def send_telegram_message(config_path: Path, message: str) -> tuple[bool, str]:
    config = load_json(config_path)
    if not config:
        return False, f"Config not found: {config_path}"

    token = str(config.get("telegram_bot_token") or "").strip()
    chat_id = str(config.get("telegram_chat_id") or "").strip()
    if not token or not chat_id:
        return False, "Telegram token or chat id is empty."

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": message,
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")

    request = urllib.request.Request(url, data=payload, method="POST")
    with urllib.request.urlopen(request, timeout=20) as response:
        body = response.read().decode("utf-8", errors="replace")
    return True, body


st.set_page_config(page_title="Telegram Template Lab", layout="wide")
st.title("Telegram Message Template Lab")
st.caption("Edit the OpenClaw Telegram message template, preview it with current stable data, and send a test message.")

context = build_context()
template_text = st.session_state.pop("telegram_template_override", None) or load_template()
config = load_json(NOTIFICATION_CONFIG_PATH) or {}
sim_config = load_json(SIM_NOTIFICATION_CONFIG_PATH) or {}

with st.sidebar:
    st.subheader("Config Status")
    st.write(f"Template file: `{TEMPLATE_PATH}`")
    st.write(f"Live config: `{NOTIFICATION_CONFIG_PATH}`")
    st.write(f"Sim config: `{SIM_NOTIFICATION_CONFIG_PATH}`")
    st.write("Live token:", mask_value(str(config.get("telegram_bot_token") or "")) or "not set")
    st.write("Live chat:", mask_value(str(config.get("telegram_chat_id") or "")) or "not set")
    st.write("Sim token:", mask_value(str(sim_config.get("telegram_bot_token") or "")) or "not set")
    st.write("Sim chat:", mask_value(str(sim_config.get("telegram_chat_id") or "")) or "not set")
    st.subheader("Available Placeholders")
    for key, value in context.items():
        st.code(f"{{{{{key}}}}}", language=None)
        st.caption(str(value))

left, right = st.columns([1.1, 0.9])

with left:
    edited_template = st.text_area("Template", value=template_text, height=420)
    action_cols = st.columns(5)
    with action_cols[0]:
        if st.button("Save Template", use_container_width=True):
            save_json(TEMPLATE_PATH, {"template": edited_template})
            st.success("Template saved.")
    with action_cols[1]:
        if st.button("Reset Default", use_container_width=True):
            save_json(TEMPLATE_PATH, {"template": DEFAULT_TEMPLATE})
            st.success("Template reset to default. Refresh the page to reload.")
    with action_cols[2]:
        if st.button("Reload From Disk", use_container_width=True):
            st.rerun()
    with action_cols[3]:
        if st.button("Load Simple Preset", use_container_width=True):
            st.session_state["telegram_template_override"] = DEFAULT_TEMPLATE
            st.rerun()
    with action_cols[4]:
        if st.button("Load Detailed Preset", use_container_width=True):
            st.session_state["telegram_template_override"] = DETAIL_TEMPLATE
            st.rerun()

with right:
    preview = render_template(edited_template, context)
    st.subheader("Preview")
    st.text_area("Rendered Message", value=preview, height=420)

    send_cols = st.columns(2)
    with send_cols[0]:
        if st.button("Send Test To Live", use_container_width=True):
            ok, result = send_telegram_message(NOTIFICATION_CONFIG_PATH, preview)
            if ok:
                st.success("Message sent to live Telegram target.")
                st.code(result, language="json")
            else:
                st.error(result)
    with send_cols[1]:
        if st.button("Send Test To Sim", use_container_width=True):
            ok, result = send_telegram_message(SIM_NOTIFICATION_CONFIG_PATH, preview)
            if ok:
                st.success("Message sent to sim Telegram target.")
                st.code(result, language="json")
            else:
                st.error(result)

st.subheader("Current Stable Data")
st.json(context)
