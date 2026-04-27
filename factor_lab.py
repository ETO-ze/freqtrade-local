from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from runtime_state import display_daemon_status, duration_label, normalize_daemon_status


ROOT = Path(__file__).resolve().parent
REPORT_ROOT = ROOT / "reports"
ML_REPORT_ROOT = ROOT / "user_data" / "reports" / "ml"

DAILY_REPORT = REPORT_ROOT / "openclaw-daily-alt-ml.json"
BEST_MODEL_REPORT = REPORT_ROOT / "openclaw-best-model-latest.json"
FAST_BEST_MODEL_REPORT = REPORT_ROOT / "openclaw-best-model-fast.json"
STABLE_BEST_MODEL_REPORT = REPORT_ROOT / "openclaw-best-model-stable.json"
FAST_STATUS_REPORT = REPORT_ROOT / "daemon" / "factor-daemon-fast-status.json"
STABLE_STATUS_REPORT = REPORT_ROOT / "daemon" / "factor-daemon-stable-status.json"
EVOLUTION_STATUS_REPORT = REPORT_ROOT / "daemon" / "factor-daemon-evolution-status.json"
AUTOTUNE_STATUS_REPORT = REPORT_ROOT / "daemon" / "factor-daemon-autotune-status.json"
BACKTEST_REPORT = REPORT_ROOT / "openclaw-auto-backtest-latest.json"
APPROVAL_REPORT = REPORT_ROOT / "openclaw-auto-approval-latest.md"
STRATEGY_REPORT = REPORT_ROOT / "openclaw-strategy-update-latest.md"
APPROVED_HISTORY_REPORT = REPORT_ROOT / "openclaw-approved-history.json"
ACTIVE_CONFIG_REPORT = ROOT / "user_data" / "config.openclaw-auto.json"
MAINSTREAM_CONFIG_REPORT = ROOT / "user_data" / "config.mainstream-auto.json"


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if path.name in {
        "factor-daemon-fast-status.json",
        "factor-daemon-stable-status.json",
        "factor-daemon-evolution-status.json",
        "factor-daemon-autotune-status.json",
    }:
        daemon_name = path.name.removesuffix("-status.json")
        return normalize_daemon_status(daemon_name, data)
    return data


def load_text(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8-sig")


def parse_dt(value: str | None) -> datetime | None:
    if not value or value == "N/A":
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%fZ"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def humanize_dt(value: str | None) -> str:
    dt = parse_dt(value)
    if not dt:
        return "N/A"
    return dt.strftime("%m-%d %H:%M:%S")


def humanize_duration(started_at: str | None, completed_at: str | None, status: str | None) -> str:
    start_dt = parse_dt(started_at)
    if not start_dt:
        return "N/A"

    end_dt = parse_dt(completed_at)
    if not end_dt and (status or "").lower() == "running":
        end_dt = datetime.now()
    if not end_dt:
        return "N/A"

    total_seconds = max(0, int((end_dt - start_dt).total_seconds()))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def estimate_next_run(next_run_after: str | None, status: dict | None) -> str:
    if next_run_after:
        return humanize_dt(next_run_after)

    status = status or {}
    if str(status.get("status", "")).lower() != "running":
        return "N/A"

    interval = status.get("interval_minutes")
    try:
        interval = int(interval)
    except (TypeError, ValueError):
        return "After current run"

    return (datetime.now()).strftime("%m-%d %H:%M:%S") + f" + {interval} min"


def list_ml_reports() -> list[Path]:
    if not ML_REPORT_ROOT.exists():
        return []
    return sorted(ML_REPORT_ROOT.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)


def build_runtime_summary(
    stable_model_data: dict | None,
    fast_model_data: dict | None,
    stable_status: dict | None,
    fast_status: dict | None,
    evolution_status: dict | None,
    autotune_status: dict | None,
) -> dict:
    stable_selected = (stable_model_data or {}).get("selected_model", "N/A")
    fast_selected = (fast_model_data or {}).get("selected_model", "N/A")
    return {
        "live_model": stable_selected if stable_selected != "N/A" else fast_selected,
        "live_source": "stable" if stable_selected != "N/A" else "fast",
        "stable_model": stable_selected,
        "fast_model": fast_selected,
        "stable_status": (stable_status or {}).get("status", "not started"),
        "fast_status": (fast_status or {}).get("status", "not started"),
        "evolution_status": (evolution_status or {}).get("status", "manual / not started"),
        "autotune_status": (autotune_status or {}).get("status", "not started"),
        "stable_generated_at": (stable_model_data or {}).get("generated_at", "N/A"),
    }


def render_metric_cards(backtest_data: dict | None, daily_data: dict | None, best_model_data: dict | None) -> None:
    col1, col2, col3, col4 = st.columns(4)

    metrics = (backtest_data or {}).get("metrics", {})
    with col1:
        st.metric("Candidate Profit", f"{metrics.get('total_profit_pct', 'N/A')}%")
    with col2:
        st.metric("Profit Factor", metrics.get("profit_factor", "N/A"))
    with col3:
        st.metric("Max Drawdown", f"{metrics.get('max_drawdown_pct', 'N/A')}%")
    with col4:
        selected = (best_model_data or {}).get("selected_model", "N/A")
        st.metric("Best Model", selected)

    if daily_data:
        st.caption(
            f"Generated {daily_data.get('generated_at', 'N/A')} | "
            f"Strategy {daily_data.get('strategy', 'N/A')}"
        )


def approval_is_approved(approval_text: str | None) -> bool:
    if not approval_text:
        return False
    lowered = approval_text.lower()
    return "approved for freqtrade auto update" in lowered


def render_runtime_summary(summary: dict) -> None:
    st.subheader("Current Runtime Model")
    left, mid, right, extra = st.columns(4)
    with left:
        st.metric("Live Factor Model", summary["live_model"])
        st.caption(f"Source: {summary['live_source']} | Stable report: {summary['stable_generated_at']}")
    with mid:
        st.metric("Fast Model", summary["fast_model"])
        st.caption(f"Fast status: {summary['fast_status']}")
    with right:
        st.metric("Stable Model", summary["stable_model"])
        st.caption(
            f"Stable status: {summary['stable_status']} | Evolution: {summary['evolution_status']}"
        )
    with extra:
        st.metric("Autotune", summary["autotune_status"])
        st.caption("Runtime tuning daemon")


def render_approved_history(history_data: list[dict] | None) -> None:
    st.subheader("Approved Factor History")
    if not history_data:
        st.info("No approved factor history yet.")
        return

    if isinstance(history_data, dict):
        history_rows = [history_data]
    else:
        history_rows = history_data

    history_df = pd.DataFrame(history_rows)
    if history_df.empty:
        st.info("No approved factor history yet.")
        return

    for _, row in history_df.iterrows():
        generated_at = row.get("generated_at", "N/A")
        best_model = row.get("best_model", "N/A")
        selected_pairs = row.get("selected_pairs", [])
        pair_text = ", ".join(selected_pairs) if isinstance(selected_pairs, list) else str(selected_pairs)

        with st.container(border=True):
            st.markdown(f"**{generated_at}**")
            subtitle_left, subtitle_right = st.columns([2, 3])
            with subtitle_left:
                st.caption(f"Model: {best_model}")
            with subtitle_right:
                st.caption(f"Strategy: {row.get('strategy', 'N/A')}")

            metric_cols = st.columns(5)
            with metric_cols[0]:
                st.metric("Profit", f"{row.get('total_profit_pct', 'N/A')}%")
            with metric_cols[1]:
                st.metric("Profit Factor", row.get("profit_factor", "N/A"))
            with metric_cols[2]:
                st.metric("Winrate", f"{row.get('winrate', 'N/A')}%")
            with metric_cols[3]:
                st.metric("Drawdown", f"{row.get('max_drawdown_pct', 'N/A')}%")
            with metric_cols[4]:
                st.metric("Trades", row.get("trade_count", "N/A"))

            st.caption(f"Pairs: {pair_text if pair_text else 'N/A'}")


def render_control_status(
    runtime_summary: dict,
    fast_status: dict | None,
    stable_status: dict | None,
    evolution_status: dict | None,
    autotune_status: dict | None,
    active_config: dict | None,
    mainstream_config: dict | None,
    approval_text: str | None,
    backtest_data: dict | None,
) -> None:
    st.subheader("OpenClaw Control Status")

    top_cols = st.columns(5)
    with top_cols[0]:
        st.metric("Live Model", runtime_summary.get("live_model", "N/A"))
    with top_cols[1]:
        st.metric("Fast Status", (fast_status or {}).get("status", "not started"))
    with top_cols[2]:
        st.metric("Stable Status", (stable_status or {}).get("status", "not started"))
    with top_cols[3]:
        st.metric("Evolution Status", (evolution_status or {}).get("status", "manual / not started"))
    with top_cols[4]:
        st.metric("Autotune Status", (autotune_status or {}).get("status", "not started"))

    status_rows = []
    for name, status in (
        ("fast", fast_status or {}),
        ("stable", stable_status or {}),
        ("evolution", evolution_status or {}),
        ("autotune", autotune_status or {}),
    ):
        if status:
            status_rows.append(
                {
                    "Service": name,
                    "Status": status.get("status", "N/A"),
                    "Run": status.get("run", "N/A"),
                    "Started": status.get("started_at", "N/A"),
                    "Completed": status.get("completed_at", "N/A"),
                    "Next Run": status.get("next_run_after", "N/A"),
                    "Error": status.get("error", "") or "",
                }
            )
    if status_rows:
        st.dataframe(pd.DataFrame(status_rows), use_container_width=True, hide_index=True)

    active_pairs = []
    strategy = "N/A"
    timeframe = "N/A"
    max_open_trades = "N/A"
    initial_state = "N/A"
    bot_name = "N/A"
    if active_config:
        strategy = active_config.get("strategy", "N/A")
        timeframe = active_config.get("timeframe", "N/A")
        max_open_trades = active_config.get("max_open_trades", "N/A")
        initial_state = active_config.get("initial_state", "N/A")
        bot_name = active_config.get("bot_name", "N/A")
        active_pairs = (active_config.get("exchange") or {}).get("pair_whitelist") or []

    st.markdown("**Active Freqtrade Config**")
    cfg_cols = st.columns(5)
    with cfg_cols[0]:
        st.metric("Bot", bot_name)
    with cfg_cols[1]:
        st.metric("Strategy", strategy)
    with cfg_cols[2]:
        st.metric("Timeframe", timeframe)
    with cfg_cols[3]:
        st.metric("Max Open Trades", max_open_trades)
    with cfg_cols[4]:
        st.metric("Initial State", initial_state)

    st.caption(f"Pairs: {', '.join(active_pairs) if active_pairs else 'N/A'}")

    st.markdown("**Mainstream Freqtrade Config**")
    mainstream_pairs = []
    mainstream_strategy = "N/A"
    mainstream_timeframe = "N/A"
    mainstream_open_trades = "N/A"
    mainstream_bot_name = "N/A"
    if mainstream_config:
        mainstream_strategy = mainstream_config.get("strategy", "N/A")
        mainstream_timeframe = mainstream_config.get("timeframe", "N/A")
        mainstream_open_trades = mainstream_config.get("max_open_trades", "N/A")
        mainstream_bot_name = mainstream_config.get("bot_name", "N/A")
        mainstream_pairs = (mainstream_config.get("exchange") or {}).get("pair_whitelist") or []

    mainstream_cols = st.columns(4)
    with mainstream_cols[0]:
        st.metric("Mainstream Bot", mainstream_bot_name)
    with mainstream_cols[1]:
        st.metric("Mainstream Strategy", mainstream_strategy)
    with mainstream_cols[2]:
        st.metric("Mainstream Timeframe", mainstream_timeframe)
    with mainstream_cols[3]:
        st.metric("Mainstream Max Open", mainstream_open_trades)
    st.caption(f"Pairs: {', '.join(mainstream_pairs) if mainstream_pairs else 'N/A'}")

    if backtest_data and approval_text:
        metrics = (backtest_data or {}).get("metrics", {})
        st.markdown("**Latest Stable Gate Result**")
        gate_cols = st.columns(8)
        with gate_cols[0]:
            st.metric("Profit", f"{metrics.get('total_profit_pct', 'N/A')}%")
        with gate_cols[1]:
            st.metric("Profit Factor", metrics.get("profit_factor", "N/A"))
        with gate_cols[2]:
            st.metric("Winrate", f"{metrics.get('winrate', 'N/A')}%")
        with gate_cols[3]:
            st.metric("Drawdown", f"{metrics.get('max_drawdown_pct', 'N/A')}%")
        with gate_cols[4]:
            st.metric("Trades", metrics.get("trade_count", "N/A"))
        with gate_cols[5]:
            st.metric("Sharpe", metrics.get("sharpe", "N/A"))
        with gate_cols[6]:
            st.metric("Sortino", metrics.get("sortino", "N/A"))
        with gate_cols[7]:
            st.metric("Calmar", metrics.get("calmar", "N/A"))
        st.caption("Stable gate: profit >= 15%, PF >= 1.9, drawdown <= 8.5%, sortino >= 7, calmar >= 45, trades >= 180")
        decision_line = next(
            (line.strip("- ").strip() for line in approval_text.splitlines() if "Decision:" in line),
            "Decision: N/A",
        )
        st.caption(decision_line)


def render_schedule_status(
    fast_status: dict | None,
    stable_status: dict | None,
    evolution_status: dict | None,
    autotune_status: dict | None,
) -> None:
    st.subheader("Runtime Schedule")

    def build_row(name: str, status: dict | None) -> dict:
        status = status or {}
        return {
            "service": name,
            "status": status.get("status", "not started"),
            "status_display": display_daemon_status(status),
            "run": status.get("run", "N/A"),
            "started_at": status.get("started_at"),
            "completed_at": status.get("completed_at"),
            "next_run_after": status.get("next_run_after"),
            "duration": humanize_duration(
                status.get("started_at"),
                status.get("completed_at"),
                status.get("status"),
            ),
            "interval_minutes": status.get("interval_minutes", "N/A"),
            "startup_delay_seconds": status.get("startup_delay_seconds", "N/A"),
            "error": status.get("error") or "",
            "next_run_display": estimate_next_run(status.get("next_run_after"), status),
        }

    rows = [
        build_row("fast", fast_status),
        build_row("stable", stable_status),
        build_row("evolution", evolution_status),
        build_row("autotune", autotune_status),
    ]

    top_cols = st.columns(4)
    for col, row in zip(top_cols, rows):
        with col:
            with st.container(border=True):
                st.markdown(f"### {row['service'].title()}")
                st.metric("Status", row["status_display"])
                st.metric(duration_label({"status": row["status"]}), row["duration"])
                st.caption(f"Run #{row['run']}")
                st.caption(f"Started: {humanize_dt(row['started_at'])}")
                st.caption(f"Completed: {humanize_dt(row['completed_at'])}")
                st.caption(f"Next Run: {row['next_run_display']}")
                st.caption(f"Interval: {row['interval_minutes']} min")
                st.caption(f"Startup Delay: {row['startup_delay_seconds']} sec")
                if row["error"]:
                    st.error(row["error"])

    schedule_df = pd.DataFrame(
        [
            {
                "Service": row["service"],
                "Status": row["status_display"],
                "Run": row["run"],
                "Started": humanize_dt(row["started_at"]),
                "Completed": humanize_dt(row["completed_at"]),
                "Next Run": row["next_run_display"],
                "Duration": row["duration"],
                "Interval (min)": row["interval_minutes"],
                "Startup Delay (sec)": row["startup_delay_seconds"],
            }
            for row in rows
        ]
    )
    st.dataframe(schedule_df, use_container_width=True, hide_index=True)


def render_bucket_section(daily_data: dict | None) -> None:
    st.subheader("OpenClaw Buckets")
    if not daily_data:
        st.info("No combined OpenClaw report found yet.")
        return

    tradable = pd.DataFrame(daily_data.get("tradable", []))
    observe = pd.DataFrame(daily_data.get("observe", []))
    pause = pd.DataFrame(daily_data.get("pause", []))

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Tradable", len(tradable))
        if not tradable.empty:
            st.dataframe(tradable[["Pair", "RobustScore", "ModelAggregateScore", "BullishVotes", "BearishVotes"]], use_container_width=True, hide_index=True)
    with col2:
        st.metric("Observe", len(observe))
        if not observe.empty:
            st.dataframe(observe[["Pair", "RobustScore", "ModelAggregateScore", "BullishVotes", "BearishVotes"]], use_container_width=True, hide_index=True)
    with col3:
        st.metric("Pause", len(pause))
        if not pause.empty:
            st.dataframe(pause[["Pair", "RobustScore", "ModelAggregateScore", "BullishVotes", "BearishVotes"]], use_container_width=True, hide_index=True)


def render_ranking_chart(daily_data: dict | None) -> None:
    st.subheader("Pair Ranking")
    if not daily_data:
        st.info("No ranking data available.")
        return

    ranking_df = pd.DataFrame(daily_data.get("ranking", []))
    if ranking_df.empty:
        st.info("Ranking is empty.")
        return

    fig = px.scatter(
        ranking_df,
        x="RobustScore",
        y="ModelAggregateScore",
        color="Decision",
        size="SignalCount",
        hover_name="Pair",
        hover_data=["LongEdge", "ShortEdge", "BullishVotes", "BearishVotes"],
        title="Robust Score vs Model Score",
    )
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(ranking_df.sort_values(["Decision", "RobustScore"], ascending=[True, False]), use_container_width=True, hide_index=True)


def render_best_model(best_model_data: dict | None) -> None:
    st.subheader("Best Model")
    if not best_model_data:
        st.info("No best-model report found yet.")
        return

    st.write(
        f"Selected model: `{best_model_data.get('selected_model', 'N/A')}` | "
        f"Weight: `{best_model_data.get('model_weight', 'N/A')}`"
    )

    models_df = pd.DataFrame(best_model_data.get("models", []))
    if not models_df.empty:
        st.dataframe(models_df.sort_values("weight", ascending=False), use_container_width=True, hide_index=True)

    factors_df = pd.DataFrame(best_model_data.get("top_factors", []))
    if not factors_df.empty:
        fig = px.bar(
            factors_df.sort_values("WeightedImportance"),
            x="WeightedImportance",
            y="Feature",
            orientation="h",
            title="Top Factors",
        )
        st.plotly_chart(fig, use_container_width=True)


def render_ml_report_viewer() -> None:
    st.subheader("Historical ML Reports")
    report_files = list_ml_reports()
    if not report_files:
        st.info("No local ML reports found.")
        return

    report_options = {path.name: path for path in report_files}
    selected_name = st.selectbox("Report", list(report_options.keys()), index=0)
    report_data = load_json(report_options[selected_name])
    if not report_data:
        st.info("Unable to load report.")
        return

    metadata = report_data.get("metadata", {})
    st.write(
        f"Samples `{metadata.get('samples', 'N/A')}` | "
        f"Timeframe `{metadata.get('timeframe', 'N/A')}` | "
        f"Horizon `{metadata.get('horizon', 'N/A')}` | "
        f"Threshold `{metadata.get('threshold', 'N/A')}`"
    )

    summary_rows = []
    for item in report_data.get("results", []):
        summary_rows.append(
            {
                "Model": item.get("model"),
                "Accuracy": item.get("accuracy"),
                "Balanced Accuracy": item.get("balanced_accuracy"),
                "Long Precision": item.get("long_precision"),
                "Short Precision": item.get("short_precision"),
                "Pred Long Avg Return": item.get("predicted_long_avg_forward_return"),
                "Pred Short Avg Return": item.get("predicted_short_avg_forward_return"),
            }
        )
    summary_df = pd.DataFrame(summary_rows)
    if not summary_df.empty:
        st.dataframe(summary_df.sort_values("Accuracy", ascending=False), use_container_width=True, hide_index=True)

    st.json(report_data)


st.set_page_config(page_title="Factor Lab Dashboard", layout="wide")
st.title("Factor Lab Dashboard")
st.caption("Read-only dashboard for OpenClaw factor training, screening, and Freqtrade promotion.")

daily_data = load_json(DAILY_REPORT)
best_model_data = load_json(BEST_MODEL_REPORT)
fast_best_model_data = load_json(FAST_BEST_MODEL_REPORT)
stable_best_model_data = load_json(STABLE_BEST_MODEL_REPORT)
fast_status_data = load_json(FAST_STATUS_REPORT)
stable_status_data = load_json(STABLE_STATUS_REPORT)
evolution_status_data = load_json(EVOLUTION_STATUS_REPORT)
autotune_status_data = load_json(AUTOTUNE_STATUS_REPORT)
backtest_data = load_json(BACKTEST_REPORT)
approval_text = load_text(APPROVAL_REPORT)
strategy_text = load_text(STRATEGY_REPORT)
approved_history_data = load_json(APPROVED_HISTORY_REPORT)
active_config_data = load_json(ACTIVE_CONFIG_REPORT)
mainstream_config_data = load_json(MAINSTREAM_CONFIG_REPORT)
runtime_summary = build_runtime_summary(
    stable_best_model_data,
    fast_best_model_data,
    stable_status_data,
    fast_status_data,
    evolution_status_data,
    autotune_status_data,
)

if approval_is_approved(approval_text):
    render_metric_cards(backtest_data, daily_data, best_model_data)
else:
    st.info("Latest candidate did not pass the promotion gate. Live configuration remains on the last approved factor set.")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Live Factor Model", runtime_summary["live_model"])
    with col2:
        st.metric("Stable Model", runtime_summary["stable_model"])

overview_tab, control_tab, schedule_tab, model_tab, history_tab, reports_tab = st.tabs(
    ["Overview", "Control Status", "Schedule", "Best Model", "History", "Reports"]
)

with overview_tab:
    render_runtime_summary(runtime_summary)
    st.divider()
    render_approved_history(approved_history_data)
    st.divider()
    render_bucket_section(daily_data)
    st.divider()
    render_ranking_chart(daily_data)

with control_tab:
    render_control_status(
        runtime_summary,
        fast_status_data,
        stable_status_data,
        evolution_status_data,
        autotune_status_data,
        active_config_data,
        mainstream_config_data,
        approval_text,
        backtest_data,
    )

with schedule_tab:
    render_schedule_status(
        fast_status_data,
        stable_status_data,
        evolution_status_data,
        autotune_status_data,
    )

with model_tab:
    render_best_model(best_model_data)

with history_tab:
    render_ml_report_viewer()

with reports_tab:
    left, right = st.columns(2)
    with left:
        st.subheader("Strategy Update")
        if strategy_text:
            st.markdown(strategy_text)
        else:
            st.info("Strategy update report not found.")
    with right:
        st.subheader("Approval Report")
        if approval_text:
            st.markdown(approval_text)
        else:
            st.info("Approval report not found.")
