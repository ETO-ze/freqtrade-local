from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


ROOT = Path(__file__).resolve().parent
REPORT_ROOT = ROOT / "reports"
ML_REPORT_ROOT = ROOT / "user_data" / "reports" / "ml"

DAILY_REPORT = REPORT_ROOT / "openclaw-daily-alt-ml.json"
BEST_MODEL_REPORT = REPORT_ROOT / "openclaw-best-model-latest.json"
BACKTEST_REPORT = REPORT_ROOT / "openclaw-auto-backtest-latest.json"
APPROVAL_REPORT = REPORT_ROOT / "openclaw-auto-approval-latest.md"
STRATEGY_REPORT = REPORT_ROOT / "openclaw-strategy-update-latest.md"


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_text(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8-sig")


def list_ml_reports() -> list[Path]:
    if not ML_REPORT_ROOT.exists():
        return []
    return sorted(ML_REPORT_ROOT.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)


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
backtest_data = load_json(BACKTEST_REPORT)
approval_text = load_text(APPROVAL_REPORT)
strategy_text = load_text(STRATEGY_REPORT)

render_metric_cards(backtest_data, daily_data, best_model_data)

overview_tab, model_tab, history_tab, reports_tab = st.tabs(
    ["Overview", "Best Model", "History", "Reports"]
)

with overview_tab:
    render_bucket_section(daily_data)
    st.divider()
    render_ranking_chart(daily_data)

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
