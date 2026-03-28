from __future__ import annotations

import copy
import json
import subprocess
import zipfile
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


ROOT = Path(__file__).resolve().parent
USER_DATA = ROOT / "user_data"
REPORT_ROOT = ROOT / "reports"
BACKTEST_ROOT = USER_DATA / "backtest_results"
STRATEGY_ROOT = USER_DATA / "strategies"

RUNTIME_POLICY_PATH = USER_DATA / "model_runtime_policy.json"
STABLE_REPORT_PATH = REPORT_ROOT / "openclaw-daily-alt-ml-stable.json"
BEST_MODEL_PATH = REPORT_ROOT / "openclaw-best-model-stable.json"
DEFAULT_CONFIG_PATH = USER_DATA / "config.backtest.alternativehunter.json"
TEMP_CONFIG_PATH = USER_DATA / "config.backtest.strategylab.json"
TEMP_POLICY_PATH = USER_DATA / "model_runtime_policy.debug.json"

DEFAULT_TUNING = {
    "stake_weight": 1.0,
    "leverage_weight": 1.0,
    "same_side_recent_boost": 0.5,
    "same_side_bias_multiplier": 4.0,
    "opposite_side_penalty": 0.45,
    "opposite_side_recent_penalty": 0.2,
    "bias_block_threshold": 0.015,
    "recent_weight_block_threshold": 0.45,
    "minimum_side_multiplier": 0.1,
}


def load_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def merged_tuning(policy_data: dict | None) -> dict:
    tuning = dict(DEFAULT_TUNING)
    payload = (policy_data or {}).get("tuning") or {}
    if isinstance(payload, dict):
        tuning.update(payload)
    return tuning


def list_strategy_names() -> list[str]:
    return sorted(path.stem for path in STRATEGY_ROOT.glob("*.py") if not path.name.startswith("__"))


def policy_frame(policy_data: dict | None) -> pd.DataFrame:
    rows: list[dict] = []
    pairs = (policy_data or {}).get("pairs", {})
    for pair, payload in pairs.items():
        rows.append(
            {
                "Pair": pair,
                "Decision": payload.get("decision", "n/a"),
                "RiskTier": payload.get("risk_tier", "n/a"),
                "DirectionBias": payload.get("direction_bias", "both"),
                "BiasStrength": float(payload.get("bias_strength", 0.0) or 0.0),
                "RecentWeight": float(payload.get("recent_weight", 0.0) or 0.0),
                "StakeScale": float(payload.get("stake_scale", 0.0) or 0.0),
                "LeverageCap": float(payload.get("leverage_cap", 0.0) or 0.0),
                "ModelScore": float(payload.get("model_score", 0.0) or 0.0),
                "RecentModelScore": float(payload.get("recent_model_score", 0.0) or 0.0),
                "RobustScore": float(payload.get("robust_score", 0.0) or 0.0),
                "LongEdge": float(payload.get("long_edge", 0.0) or 0.0),
                "ShortEdge": float(payload.get("short_edge", 0.0) or 0.0),
                "RecentLongEdge": float(payload.get("recent_long_edge", 0.0) or 0.0),
                "RecentShortEdge": float(payload.get("recent_short_edge", 0.0) or 0.0),
                "BullishVotes": int(payload.get("bullish_votes", 0) or 0),
                "BearishVotes": int(payload.get("bearish_votes", 0) or 0),
                "AllowLong": bool(payload.get("allow_long", True)),
                "AllowShort": bool(payload.get("allow_short", True)),
                "Blocked": bool(payload.get("blocked", False)),
            }
        )

    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    return frame.sort_values(["Decision", "RecentModelScore", "ModelScore"], ascending=[True, False, False])


def latest_backtest_zip() -> Path | None:
    if not BACKTEST_ROOT.exists():
        return None
    files = sorted(BACKTEST_ROOT.glob("backtest-result-*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def parse_backtest_zip(zip_path: Path) -> dict | None:
    if not zip_path or not zip_path.exists():
        return None

    with zipfile.ZipFile(zip_path) as zf:
        json_names = [name for name in zf.namelist() if name.endswith(".json") and "_config" not in name]
        if not json_names:
            return None
        payload = json.loads(zf.read(json_names[0]).decode("utf-8"))

    strategy_block = payload.get("strategy", {})
    if not strategy_block:
        return None
    strategy_name = next(iter(strategy_block))
    strategy_data = strategy_block[strategy_name]
    pair_rows = strategy_data.get("results_per_pair", [])
    pair_frame = pd.DataFrame([row for row in pair_rows if row.get("key") != "TOTAL"])

    return {
        "strategy_name": strategy_name,
        "metrics": {
            "total_profit_pct": round(float(strategy_data.get("profit_total", 0.0) or 0.0) * 100, 2),
            "profit_factor": round(float(strategy_data.get("profit_factor", 0.0) or 0.0), 4),
            "winrate_pct": round(float(strategy_data.get("winrate", 0.0) or 0.0) * 100, 2),
            "max_drawdown_pct": round(float(strategy_data.get("max_drawdown_account", 0.0) or 0.0) * 100, 2),
            "trade_count": int(strategy_data.get("total_trades", 0) or 0),
            "profit_long_pct": round(float(strategy_data.get("profit_total_long", 0.0) or 0.0) * 100, 2),
            "profit_short_pct": round(float(strategy_data.get("profit_total_short", 0.0) or 0.0) * 100, 2),
            "timerange": strategy_data.get("timerange", "n/a"),
            "timeframe": strategy_data.get("timeframe", "n/a"),
        },
        "pair_frame": pair_frame,
        "raw": strategy_data,
    }


def build_temp_backtest_config(
    base_config_path: Path,
    strategy_name: str,
    selected_pairs: list[str],
    max_open_trades: int,
    stake_amount: float,
) -> dict:
    base_config = load_json(base_config_path)
    if not isinstance(base_config, dict):
        raise RuntimeError(f"Unable to load base config: {base_config_path}")

    config = copy.deepcopy(base_config)
    config["bot_name"] = "freqtrade-backtest-strategylab"
    config["strategy"] = strategy_name
    config["max_open_trades"] = int(max_open_trades)
    config["stake_amount"] = float(stake_amount)
    config.setdefault("exchange", {})
    config["exchange"]["pair_whitelist"] = selected_pairs
    return config


def run_backtest(
    strategy_name: str,
    timerange: str,
    base_config_path: Path,
    selected_pairs: list[str],
    max_open_trades: int,
    stake_amount: float,
    policy_data: dict | None,
    tuning: dict,
) -> tuple[int, str, str, Path]:
    config = build_temp_backtest_config(
        base_config_path=base_config_path,
        strategy_name=strategy_name,
        selected_pairs=selected_pairs,
        max_open_trades=max_open_trades,
        stake_amount=stake_amount,
    )
    save_json(TEMP_CONFIG_PATH, config)

    debug_policy = copy.deepcopy(policy_data or {})
    debug_policy["tuning"] = tuning
    save_json(TEMP_POLICY_PATH, debug_policy)

    command = [
        "docker",
        "run",
        "--rm",
        "-e",
        "FT_RUNTIME_POLICY_PATH=/freqtrade/user_data/model_runtime_policy.debug.json",
        "-v",
        f"{USER_DATA}:/freqtrade/user_data",
        "freqtradeorg/freqtrade:stable",
        "backtesting",
        "--config",
        "/freqtrade/user_data/config.backtest.strategylab.json",
        "--strategy",
        strategy_name,
        "--timerange",
        str(timerange),
        "--export",
        "trades",
    ]

    result = subprocess.run(command, capture_output=True, text=True, cwd=ROOT)
    return result.returncode, result.stdout, result.stderr, latest_backtest_zip() or TEMP_CONFIG_PATH


def render_policy_cards(frame: pd.DataFrame) -> None:
    if frame.empty:
        st.info("No runtime policy available yet.")
        return

    tradable = int((frame["Decision"] == "tradable").sum())
    observe = int((frame["Decision"] == "observe").sum())
    pause = int((frame["Decision"] == "pause").sum())
    blocked = int(frame["Blocked"].sum())

    cols = st.columns(4)
    cols[0].metric("Tradable", tradable)
    cols[1].metric("Observe", observe)
    cols[2].metric("Pause", pause)
    cols[3].metric("Blocked", blocked)


def render_tuning_summary(tuning: dict) -> None:
    st.subheader("Tuning Summary")
    cols = st.columns(5)
    cols[0].metric("Stake Weight", tuning["stake_weight"])
    cols[1].metric("Leverage Weight", tuning["leverage_weight"])
    cols[2].metric("Bias Threshold", tuning["bias_block_threshold"])
    cols[3].metric("Recent Threshold", tuning["recent_weight_block_threshold"])
    cols[4].metric("Opposite Penalty", tuning["opposite_side_penalty"])


def render_pair_scatter(frame: pd.DataFrame) -> None:
    if frame.empty:
        return

    fig = px.scatter(
        frame,
        x="RecentModelScore",
        y="ModelScore",
        color="Decision",
        size="StakeScale",
        hover_name="Pair",
        hover_data=["DirectionBias", "LeverageCap", "BiasStrength", "RecentWeight"],
        title="Model Score vs Recent Score",
    )
    st.plotly_chart(fig, use_container_width=True)


def render_pair_detail(frame: pd.DataFrame) -> None:
    if frame.empty:
        return

    pair = st.selectbox("Pair Detail", frame["Pair"].tolist(), index=0)
    row = frame.loc[frame["Pair"] == pair].iloc[0]
    cols = st.columns(4)
    cols[0].metric("Decision", row["Decision"])
    cols[1].metric("Bias", row["DirectionBias"])
    cols[2].metric("Stake Scale", row["StakeScale"])
    cols[3].metric("Leverage Cap", row["LeverageCap"])

    st.dataframe(
        pd.DataFrame(
            [
                {"Field": "ModelScore", "Value": f"{row['ModelScore']:.4f}"},
                {"Field": "RecentModelScore", "Value": f"{row['RecentModelScore']:.4f}"},
                {"Field": "RobustScore", "Value": f"{row['RobustScore']:.2f}"},
                {"Field": "BiasStrength", "Value": f"{row['BiasStrength']:.4f}"},
                {"Field": "RecentWeight", "Value": f"{row['RecentWeight']:.4f}"},
                {"Field": "LongEdge", "Value": f"{row['LongEdge']:.4f}"},
                {"Field": "ShortEdge", "Value": f"{row['ShortEdge']:.4f}"},
                {"Field": "RecentLongEdge", "Value": f"{row['RecentLongEdge']:.4f}"},
                {"Field": "RecentShortEdge", "Value": f"{row['RecentShortEdge']:.4f}"},
                {"Field": "BullishVotes", "Value": str(row["BullishVotes"])},
                {"Field": "BearishVotes", "Value": str(row["BearishVotes"])},
                {"Field": "AllowLong", "Value": "yes" if row["AllowLong"] else "no"},
                {"Field": "AllowShort", "Value": "yes" if row["AllowShort"] else "no"},
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )


def render_backtest_summary(backtest: dict | None) -> None:
    if not backtest:
        st.info("No backtest result found yet.")
        return

    metrics = backtest["metrics"]
    cols = st.columns(6)
    cols[0].metric("Profit", f"{metrics['total_profit_pct']}%")
    cols[1].metric("PF", metrics["profit_factor"])
    cols[2].metric("Winrate", f"{metrics['winrate_pct']}%")
    cols[3].metric("Drawdown", f"{metrics['max_drawdown_pct']}%")
    cols[4].metric("Trades", metrics["trade_count"])
    cols[5].metric("Long / Short", f"{metrics['profit_long_pct']} / {metrics['profit_short_pct']}")

    pair_frame = backtest["pair_frame"]
    if not pair_frame.empty:
        st.subheader("Pair Result Breakdown")
        display_frame = pair_frame[["key", "trades", "profit_total_pct", "winrate", "profit_factor", "max_drawdown_account"]].copy()
        display_frame["winrate"] = (display_frame["winrate"] * 100).round(2)
        display_frame["max_drawdown_account"] = (display_frame["max_drawdown_account"] * 100).round(2)
        display_frame = display_frame.rename(
            columns={
                "key": "Pair",
                "trades": "Trades",
                "profit_total_pct": "ProfitPct",
                "winrate": "WinratePct",
                "profit_factor": "ProfitFactor",
                "max_drawdown_account": "DrawdownPct",
            }
        )
        st.dataframe(display_frame.sort_values("ProfitPct", ascending=False), use_container_width=True, hide_index=True)


st.set_page_config(page_title="Strategy Debug Lab", page_icon=":bar_chart:", layout="wide")
st.title("Strategy Debug Lab")
st.caption("Visual debugging panel for AlternativeHunter runtime policy, tuning weights, and one-click backtests.")

policy_data = load_json(RUNTIME_POLICY_PATH)
stable_data = load_json(STABLE_REPORT_PATH)
best_model = load_json(BEST_MODEL_PATH)
frame = policy_frame(policy_data if isinstance(policy_data, dict) else {})
latest_backtest = parse_backtest_zip(latest_backtest_zip()) if latest_backtest_zip() else None
current_tuning = merged_tuning(policy_data if isinstance(policy_data, dict) else {})

strategy_names = list_strategy_names()
tradable_pairs = frame.loc[frame["Decision"] == "tradable", "Pair"].tolist() if not frame.empty else []
default_pairs = tradable_pairs or frame["Pair"].tolist()[:8] if not frame.empty else []

with st.sidebar:
    st.header("Backtest Controls")
    strategy_name = st.selectbox("Strategy", strategy_names, index=strategy_names.index("AlternativeHunter") if "AlternativeHunter" in strategy_names else 0)
    timerange = st.text_input("Timerange", value="20251201-20260318")
    base_config_path = Path(st.text_input("Base Config", value=str(DEFAULT_CONFIG_PATH)))
    max_open_trades = st.slider("Max Open Trades", min_value=1, max_value=10, value=5)
    stake_amount = st.number_input("Stake Amount", min_value=10.0, max_value=500.0, value=50.0, step=10.0)
    selected_pairs = st.multiselect("Pairs", frame["Pair"].tolist() if not frame.empty else [], default=default_pairs)

    st.divider()
    st.subheader("Tuning Weights")
    stake_weight = st.slider("Stake Weight", min_value=0.0, max_value=2.0, value=float(current_tuning["stake_weight"]), step=0.05)
    leverage_weight = st.slider("Leverage Weight", min_value=0.0, max_value=2.0, value=float(current_tuning["leverage_weight"]), step=0.05)
    same_side_recent_boost = st.slider("Same-side Recent Boost", min_value=0.0, max_value=1.5, value=float(current_tuning["same_side_recent_boost"]), step=0.05)
    same_side_bias_multiplier = st.slider("Same-side Bias Multiplier", min_value=0.0, max_value=8.0, value=float(current_tuning["same_side_bias_multiplier"]), step=0.1)
    opposite_side_penalty = st.slider("Opposite-side Penalty", min_value=0.0, max_value=1.0, value=float(current_tuning["opposite_side_penalty"]), step=0.05)
    opposite_side_recent_penalty = st.slider("Opposite-side Recent Penalty", min_value=0.0, max_value=1.0, value=float(current_tuning["opposite_side_recent_penalty"]), step=0.05)
    bias_block_threshold = st.slider("Bias Block Threshold", min_value=0.0, max_value=0.1, value=float(current_tuning["bias_block_threshold"]), step=0.001, format="%.3f")
    recent_weight_block_threshold = st.slider("Recent Weight Block Threshold", min_value=0.0, max_value=1.0, value=float(current_tuning["recent_weight_block_threshold"]), step=0.01)
    minimum_side_multiplier = st.slider("Minimum Side Multiplier", min_value=0.0, max_value=0.5, value=float(current_tuning["minimum_side_multiplier"]), step=0.01)
    tuning = {
        "stake_weight": stake_weight,
        "leverage_weight": leverage_weight,
        "same_side_recent_boost": same_side_recent_boost,
        "same_side_bias_multiplier": same_side_bias_multiplier,
        "opposite_side_penalty": opposite_side_penalty,
        "opposite_side_recent_penalty": opposite_side_recent_penalty,
        "bias_block_threshold": bias_block_threshold,
        "recent_weight_block_threshold": recent_weight_block_threshold,
        "minimum_side_multiplier": minimum_side_multiplier,
    }
    run_button = st.button("Run Backtest", type="primary", use_container_width=True)

overview_tab, pair_tab, backtest_tab = st.tabs(["Policy Overview", "Pair Detail", "Backtest"])

with overview_tab:
    if isinstance(best_model, dict):
        top_cols = st.columns(3)
        top_cols[0].metric("Stable Best Model", best_model.get("selected_model", "N/A"))
        top_cols[1].metric("Model Weight", best_model.get("model_weight", "N/A"))
        top_cols[2].metric("Generated", best_model.get("generated_at", "N/A"))
    render_policy_cards(frame)
    render_tuning_summary(tuning)
    render_pair_scatter(frame)
    if not frame.empty:
        st.subheader("Runtime Policy Table")
        st.dataframe(frame, use_container_width=True, hide_index=True)

with pair_tab:
    render_pair_detail(frame)
    if isinstance(stable_data, dict):
        top_factors = stable_data.get("top_factors", [])
        if top_factors:
            st.subheader("Top Factors")
            st.dataframe(pd.DataFrame(top_factors), use_container_width=True, hide_index=True)

with backtest_tab:
    if run_button:
        if not selected_pairs:
            st.error("Select at least one pair before running a backtest.")
        else:
            with st.spinner("Running backtest..."):
                code, stdout, stderr, result_path = run_backtest(
                    strategy_name=strategy_name,
                    timerange=timerange,
                    base_config_path=base_config_path,
                    selected_pairs=selected_pairs,
                    max_open_trades=max_open_trades,
                    stake_amount=stake_amount,
                    policy_data=policy_data if isinstance(policy_data, dict) else {},
                    tuning=tuning,
                )
            if code == 0:
                st.success(f"Backtest finished. Result: {result_path.name}")
                latest_backtest = parse_backtest_zip(result_path if result_path.suffix == ".zip" else latest_backtest_zip())
            else:
                st.error("Backtest failed.")
                st.code(stderr or stdout or "No output", language="text")

    render_backtest_summary(latest_backtest)
    if latest_backtest:
        st.caption(
            f"Latest strategy: {latest_backtest['strategy_name']} | "
            f"Timerange: {latest_backtest['metrics']['timerange']} | "
            f"Timeframe: {latest_backtest['metrics']['timeframe']}"
        )

    st.subheader("Generated Temp Config")
    if TEMP_CONFIG_PATH.exists():
        st.code(TEMP_CONFIG_PATH.read_text(encoding="utf-8"), language="json")
    else:
        st.info("Temp config will appear here after the first run.")

    st.subheader("Generated Debug Policy")
    if TEMP_POLICY_PATH.exists():
        st.code(TEMP_POLICY_PATH.read_text(encoding="utf-8"), language="json")
    else:
        st.info("Debug policy will appear here after the first run.")
