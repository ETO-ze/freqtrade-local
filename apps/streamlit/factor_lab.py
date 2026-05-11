from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import sys
import zipfile

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime_state import display_daemon_status, duration_label, normalize_daemon_status


REPORT_ROOT = ROOT / "reports"
ML_REPORT_ROOT = ROOT / "user_data" / "reports" / "ml"
BACKTEST_RESULT_ROOT = ROOT / "user_data" / "backtest_results"

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
RUNTIME_POLICY_REPORT = ROOT / "user_data" / "model_runtime_policy.json"
PROJECT_ROADMAP_REPORT = ROOT / "PROJECT_ROADMAP.json"


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


def safe_float(value, default: float | None = None) -> float | None:
    try:
        if value in (None, "", "N/A", "n/a"):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def metric_text(value, suffix: str = "") -> str:
    if value in (None, "", "N/A", "n/a"):
        return "N/A"
    return f"{value}{suffix}"


def approved_rows(history_data: list[dict] | dict | None) -> list[dict]:
    if not history_data:
        return []
    if isinstance(history_data, dict):
        return [history_data]
    return [item for item in history_data if isinstance(item, dict)]


def best_approved_factor(history_data: list[dict] | dict | None, runtime_policy: dict | None) -> dict:
    policy_factor = (runtime_policy or {}).get("active_approved_factor")
    if isinstance(policy_factor, dict) and policy_factor:
        return policy_factor

    rows = approved_rows(history_data)
    if not rows:
        return {}
    return max(rows, key=lambda item: safe_float(item.get("total_profit_pct"), -999999) or -999999)


def approval_line(approval_text: str | None, prefix: str) -> str:
    if not approval_text:
        return "N/A"
    for line in approval_text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith(prefix.lower()):
            return stripped.strip("- ").strip()
    return "N/A"


def approval_summary_rows(approval_text: str | None) -> list[dict]:
    if not approval_text:
        return []
    prefixes = (
        "- Thresholds:",
        "- Experimental high-profit bypass:",
        "- Promotion protection:",
        "- Decision:",
    )
    rows = []
    for prefix in prefixes:
        value = approval_line(approval_text, prefix)
        if value != "N/A":
            label, _, detail = value.partition(":")
            rows.append({"Rule": label, "Detail": detail.strip() or value})
    return rows


def latest_candidate_metrics(backtest_data: dict | None) -> dict:
    metrics = (backtest_data or {}).get("metrics") or {}
    return {
        "generated_at": (backtest_data or {}).get("generated_at", "N/A"),
        "model": "candidate",
        "profit": metrics.get("total_profit_pct"),
        "pf": metrics.get("profit_factor"),
        "winrate": metrics.get("winrate"),
        "drawdown": metrics.get("max_drawdown_pct"),
        "trades": metrics.get("trade_count"),
        "timerange": (backtest_data or {}).get("timerange", "N/A"),
        "result": (backtest_data or {}).get("latest_backtest", "N/A"),
    }


def approved_factor_metrics(factor: dict | None) -> dict:
    factor = factor or {}
    return {
        "generated_at": factor.get("generated_at", "N/A"),
        "model": factor.get("best_model") or factor.get("model") or "N/A",
        "profit": factor.get("total_profit_pct"),
        "pf": factor.get("profit_factor"),
        "winrate": factor.get("winrate") or factor.get("winrate_pct"),
        "drawdown": factor.get("max_drawdown_pct"),
        "trades": factor.get("trade_count"),
        "timerange": factor.get("timerange", "N/A"),
        "result": factor.get("latest_backtest", "N/A"),
        "pairs": factor.get("selected_pairs") or [],
    }


def resolve_backtest_zip(backtest_data: dict | None) -> Path | None:
    latest = (backtest_data or {}).get("latest_backtest")
    candidates: list[Path] = []
    if latest:
        latest_path = Path(str(latest))
        candidates.append(latest_path if latest_path.is_absolute() else BACKTEST_RESULT_ROOT / latest_path)
    if BACKTEST_RESULT_ROOT.exists():
        candidates.extend(sorted(BACKTEST_RESULT_ROOT.glob("*.zip"), key=lambda path: path.stat().st_mtime, reverse=True))
    for path in candidates:
        if path.exists() and path.suffix.lower() == ".zip":
            return path
    return None


@st.cache_data(show_spinner=False)
def read_backtest_zip(zip_path: str, mtime: float) -> dict:
    path = Path(zip_path)
    with zipfile.ZipFile(path) as archive:
        result_names = [
            name
            for name in archive.namelist()
            if name.endswith(".json") and not name.endswith("_config.json")
        ]
        if not result_names:
            return {}
        data = json.loads(archive.read(result_names[0]).decode("utf-8"))

    strategy_map = data.get("strategy") or {}
    if not strategy_map:
        return {}
    strategy_name, strategy = next(iter(strategy_map.items()))
    return {
        "zip_path": str(path),
        "result_file": result_names[0],
        "strategy_name": strategy_name,
        "strategy": strategy,
    }


def load_backtest_detail(backtest_data: dict | None) -> dict:
    zip_path = resolve_backtest_zip(backtest_data)
    if not zip_path:
        return {}
    try:
        bundle = read_backtest_zip(str(zip_path), zip_path.stat().st_mtime)
    except Exception as exc:
        return {"error": str(exc), "zip_path": str(zip_path)}
    return bundle


def build_daily_equity(strategy: dict) -> pd.DataFrame:
    starting_balance = safe_float(strategy.get("starting_balance"), 0) or 0
    rows = []
    for item in strategy.get("daily_profit") or []:
        if not isinstance(item, list) or len(item) < 2:
            continue
        rows.append({"date": item[0], "profit_abs": safe_float(item[1], 0) or 0})
    daily_df = pd.DataFrame(rows)
    if daily_df.empty:
        return daily_df
    daily_df["date"] = pd.to_datetime(daily_df["date"], errors="coerce")
    daily_df = daily_df.dropna(subset=["date"]).sort_values("date")
    daily_df["equity"] = starting_balance + daily_df["profit_abs"].cumsum()
    daily_df["peak"] = daily_df["equity"].cummax()
    daily_df["drawdown_abs"] = daily_df["equity"] - daily_df["peak"]
    daily_df["drawdown_pct"] = (daily_df["drawdown_abs"] / daily_df["peak"].replace(0, pd.NA) * 100).fillna(0)
    daily_df["profit_pct_of_start"] = daily_df["profit_abs"] / starting_balance * 100 if starting_balance else 0
    return daily_df


def build_trades_df(strategy: dict) -> pd.DataFrame:
    trades_df = pd.DataFrame(strategy.get("trades") or [])
    if trades_df.empty:
        return trades_df
    trades_df["close_date"] = pd.to_datetime(trades_df.get("close_date"), errors="coerce", utc=True)
    trades_df["open_date"] = pd.to_datetime(trades_df.get("open_date"), errors="coerce", utc=True)
    trades_df["profit_abs"] = pd.to_numeric(trades_df.get("profit_abs"), errors="coerce").fillna(0)
    trades_df["profit_ratio"] = pd.to_numeric(trades_df.get("profit_ratio"), errors="coerce").fillna(0)
    trades_df["is_short"] = trades_df.get("is_short", False).fillna(False).astype(bool)
    return trades_df


def build_side_stats(trades_df: pd.DataFrame) -> pd.DataFrame:
    if trades_df.empty:
        return pd.DataFrame()
    rows = []
    for is_short, group in trades_df.groupby("is_short"):
        wins = int((group["profit_abs"] > 0).sum())
        losses = int((group["profit_abs"] < 0).sum())
        trades = int(len(group))
        rows.append(
            {
                "Side": "Short" if is_short else "Long",
                "Trades": trades,
                "Wins": wins,
                "Losses": losses,
                "Winrate %": round(wins / trades * 100, 2) if trades else 0,
                "Profit USDT": round(group["profit_abs"].sum(), 4),
                "Avg Profit %": round(group["profit_ratio"].mean() * 100, 3),
                "Avg Leverage": round(pd.to_numeric(group.get("leverage"), errors="coerce").fillna(0).mean(), 3),
            }
        )
    return pd.DataFrame(rows)


def build_pair_trade_stats(trades_df: pd.DataFrame) -> pd.DataFrame:
    if trades_df.empty:
        return pd.DataFrame()
    rows = []
    for pair, group in trades_df.groupby("pair"):
        wins = int((group["profit_abs"] > 0).sum())
        losses = int((group["profit_abs"] < 0).sum())
        trades = int(len(group))
        rows.append(
            {
                "Pair": pair,
                "Trades": trades,
                "Wins": wins,
                "Losses": losses,
                "Winrate %": round(wins / trades * 100, 2) if trades else 0,
                "Profit USDT": round(group["profit_abs"].sum(), 4),
                "Avg Profit %": round(group["profit_ratio"].mean() * 100, 3),
                "Long Trades": int((~group["is_short"]).sum()),
                "Short Trades": int(group["is_short"].sum()),
            }
        )
    return pd.DataFrame(rows).sort_values("Profit USDT", ascending=False)


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
    return (
        "approved for freqtrade auto update" in lowered
        or "experimental_high_profit" in lowered
        or "experimental high-profit" in lowered
    )


def has_approved_history(history_data: list[dict] | dict | None) -> bool:
    if not history_data:
        return False
    if isinstance(history_data, dict):
        return bool(history_data)
    return len(history_data) > 0


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


def render_project_roadmap(roadmap_data: dict | None) -> None:
    st.subheader("Project Roadmap")
    items = (roadmap_data or {}).get("items") or []
    if not items:
        st.info("No project roadmap marker found.")
        return
    for item in items:
        if not isinstance(item, dict):
            continue
        with st.container(border=True):
            st.markdown(f"**{item.get('title', item.get('id', 'Unknown'))}**")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Status", item.get("status_label") or item.get("status", "N/A"))
            with col2:
                st.metric("Enabled", "yes" if item.get("enabled") else "no")
            with col3:
                st.metric("Priority", item.get("priority", "N/A"))
            st.caption(item.get("summary", ""))
            st.caption(f"Current: {item.get('current_state', 'N/A')}")
            st.caption(f"Next: {item.get('next_step', 'N/A')}")


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
                mode = row.get("approval_mode") or row.get("mode") or "standard"
                st.caption(f"Strategy: {row.get('strategy', 'N/A')} | Mode: {mode}")

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


def render_candidate_decision(
    backtest_data: dict | None,
    approved_history: list[dict] | dict | None,
    runtime_policy: dict | None,
    approval_text: str | None,
) -> None:
    st.subheader("Candidate vs Active Decision")

    candidate = latest_candidate_metrics(backtest_data)
    active = approved_factor_metrics(best_approved_factor(approved_history, runtime_policy))

    cand_profit = safe_float(candidate.get("profit"))
    active_profit = safe_float(active.get("profit"))
    profit_delta = None
    if cand_profit is not None and active_profit is not None:
        profit_delta = round(cand_profit - active_profit, 2)

    left, right, result = st.columns([2, 2, 2])
    with left:
        st.markdown("**Latest Candidate**")
        st.metric("Profit", metric_text(candidate["profit"], "%"))
        st.metric("Profit Factor", metric_text(candidate["pf"]))
        st.metric("Drawdown", metric_text(candidate["drawdown"], "%"))
        st.caption(f"Trades: {metric_text(candidate['trades'])} | Timerange: {candidate['timerange']}")
    with right:
        st.markdown("**Current / Best Approved**")
        st.metric("Profit", metric_text(active["profit"], "%"))
        st.metric("Profit Factor", metric_text(active["pf"]))
        st.metric("Drawdown", metric_text(active["drawdown"], "%"))
        st.caption(f"Trades: {metric_text(active['trades'])} | Generated: {active['generated_at']}")
    with result:
        decision = approval_line(approval_text, "- Decision:")
        protection = approval_line(approval_text, "- Protection decision:")
        approval_mode = approval_line(approval_text, "- Approval mode:")
        st.markdown("**Decision Explanation**")
        st.metric("Profit Delta", "N/A" if profit_delta is None else f"{profit_delta:+.2f}%")
        st.caption(decision)
        st.caption(protection)
        st.caption(approval_mode)

    comparison_rows = [
        {
            "Metric": "Profit %",
            "Candidate": candidate["profit"],
            "Active": active["profit"],
            "Delta": profit_delta,
        },
        {
            "Metric": "Profit Factor",
            "Candidate": candidate["pf"],
            "Active": active["pf"],
            "Delta": None
            if safe_float(candidate["pf"]) is None or safe_float(active["pf"]) is None
            else round((safe_float(candidate["pf"]) or 0) - (safe_float(active["pf"]) or 0), 3),
        },
        {
            "Metric": "Winrate %",
            "Candidate": candidate["winrate"],
            "Active": active["winrate"],
            "Delta": None
            if safe_float(candidate["winrate"]) is None or safe_float(active["winrate"]) is None
            else round((safe_float(candidate["winrate"]) or 0) - (safe_float(active["winrate"]) or 0), 2),
        },
        {
            "Metric": "Drawdown %",
            "Candidate": candidate["drawdown"],
            "Active": active["drawdown"],
            "Delta": None
            if safe_float(candidate["drawdown"]) is None or safe_float(active["drawdown"]) is None
            else round((safe_float(candidate["drawdown"]) or 0) - (safe_float(active["drawdown"]) or 0), 2),
        },
        {
            "Metric": "Trades",
            "Candidate": candidate["trades"],
            "Active": active["trades"],
            "Delta": None
            if safe_float(candidate["trades"]) is None or safe_float(active["trades"]) is None
            else int((safe_float(candidate["trades"]) or 0) - (safe_float(active["trades"]) or 0)),
        },
    ]
    st.dataframe(pd.DataFrame(comparison_rows), use_container_width=True, hide_index=True)

    rule_rows = approval_summary_rows(approval_text)
    if rule_rows:
        st.markdown("**Actual Gate Rules From Latest Approval Report**")
        st.dataframe(pd.DataFrame(rule_rows), use_container_width=True, hide_index=True)

    pairs = active.get("pairs") or []
    if pairs:
        st.caption(f"Active approved pairs: {', '.join(pairs)}")


def render_data_quality(backtest_data: dict | None, approval_text: str | None) -> None:
    st.subheader("Backtest Data Quality")
    if not backtest_data:
        st.info("No latest backtest report found.")
        return

    freshest = approval_line(approval_text, "- Freshest market timestamp:")
    cols = st.columns(5)
    with cols[0]:
        st.metric("Timerange", backtest_data.get("timerange", "N/A"))
    with cols[1]:
        st.metric("Cache", backtest_data.get("cache_status", "N/A"))
    with cols[2]:
        st.metric("Generated", humanize_dt(backtest_data.get("generated_at")))
    with cols[3]:
        st.metric("Freshest Market", freshest.replace("Freshest market timestamp:", "").strip() if freshest != "N/A" else "N/A")
    with cols[4]:
        st.metric("Max Open", ((backtest_data.get("metrics") or {}).get("max_open_trades", "N/A")))

    st.caption(f"Candidate config: {backtest_data.get('config_path', 'N/A')}")
    st.caption(f"Result zip: {backtest_data.get('latest_backtest', 'N/A')}")
    cache_key = str(backtest_data.get("cache_key", "N/A"))
    st.caption(f"Cache key: {cache_key[:16]}..." if cache_key != "N/A" else "Cache key: N/A")


def render_factor_health(best_model_data: dict | None) -> None:
    st.subheader("Factor Health")
    if not best_model_data:
        st.info("No best-model report found yet.")
        return

    models_df = pd.DataFrame(best_model_data.get("models", []))
    if models_df.empty:
        st.info("No model diagnostics found.")
        return

    selected_cols = [
        "model",
        "weight",
        "accuracy",
        "balanced_accuracy",
        "long_precision",
        "short_precision",
        "top_feature_name",
        "top_feature_share",
        "top3_feature_share",
        "mark_premium_family_share",
        "orthogonal_feature_share",
    ]
    display_cols = [col for col in selected_cols if col in models_df.columns]
    st.dataframe(models_df[display_cols].sort_values("weight", ascending=False), use_container_width=True, hide_index=True)

    warnings = []
    for _, row in models_df.iterrows():
        model = row.get("model", "model")
        mark_share = safe_float(row.get("mark_premium_family_share"), 0) or 0
        top3_share = safe_float(row.get("top3_feature_share"), 0) or 0
        orthogonal_share = safe_float(row.get("orthogonal_feature_share"), 0) or 0
        if mark_share >= 0.6:
            warnings.append(f"{model}: mark_premium family share is high ({mark_share:.2f}).")
        if top3_share >= 0.8:
            warnings.append(f"{model}: top-3 factor concentration is high ({top3_share:.2f}).")
        if orthogonal_share <= 0.1:
            warnings.append(f"{model}: orthogonal factor share is low ({orthogonal_share:.2f}).")

    if warnings:
        st.warning("\n".join(f"- {item}" for item in warnings))
    else:
        st.success("No obvious factor concentration warnings.")


def render_backtest_detail(backtest_data: dict | None) -> None:
    st.subheader("Backtest Result Detail")
    detail = load_backtest_detail(backtest_data)
    if not detail:
        st.info("No Freqtrade backtest zip found.")
        return
    if detail.get("error"):
        st.error(f"Unable to read backtest zip: {detail['error']}")
        st.caption(detail.get("zip_path", ""))
        return

    strategy = detail.get("strategy") or {}
    trades_df = build_trades_df(strategy)
    daily_df = build_daily_equity(strategy)
    pair_df = pd.DataFrame(strategy.get("results_per_pair") or [])

    st.caption(
        f"Source: {Path(detail.get('zip_path', '')).name} | "
        f"Strategy: {detail.get('strategy_name', 'N/A')} | "
        f"Result JSON: {detail.get('result_file', 'N/A')}"
    )

    overview_cols = st.columns(6)
    with overview_cols[0]:
        st.metric("Trades", strategy.get("total_trades", "N/A"))
    with overview_cols[1]:
        st.metric("Long", strategy.get("trade_count_long", "N/A"))
    with overview_cols[2]:
        st.metric("Short", strategy.get("trade_count_short", "N/A"))
    with overview_cols[3]:
        st.metric("Profit Factor", strategy.get("profit_factor", "N/A"))
    with overview_cols[4]:
        st.metric("Final Balance", round(safe_float(strategy.get("final_balance"), 0) or 0, 3))
    with overview_cols[5]:
        st.metric("Max Drawdown", f"{round((safe_float(strategy.get('max_drawdown_account'), 0) or 0) * 100, 2)}%")

    if not daily_df.empty:
        equity_fig = px.line(
            daily_df,
            x="date",
            y="equity",
            title="Equity Curve",
            labels={"date": "Date", "equity": "Balance"},
        )
        st.plotly_chart(equity_fig, use_container_width=True)

        drawdown_fig = px.area(
            daily_df,
            x="date",
            y="drawdown_pct",
            title="Drawdown Curve",
            labels={"date": "Date", "drawdown_pct": "Drawdown %"},
        )
        st.plotly_chart(drawdown_fig, use_container_width=True)

    st.markdown("**Pair-level Profit Ranking**")
    if not pair_df.empty:
        pair_df = pair_df[pair_df.get("key") != "TOTAL"].copy()
        display_cols = [
            "key",
            "trades",
            "profit_total_pct",
            "profit_total_abs",
            "winrate",
            "profit_factor",
            "max_drawdown_abs",
        ]
        display_cols = [col for col in display_cols if col in pair_df.columns]
        if "winrate" in pair_df.columns:
            pair_df["winrate_pct"] = (pd.to_numeric(pair_df["winrate"], errors="coerce") * 100).round(2)
            display_cols = ["key", "trades", "profit_total_pct", "profit_total_abs", "winrate_pct", "profit_factor", "max_drawdown_abs"]
            display_cols = [col for col in display_cols if col in pair_df.columns]
        st.dataframe(
            pair_df[display_cols].sort_values("profit_total_abs", ascending=False),
            use_container_width=True,
            hide_index=True,
        )
        chart_df = pair_df.sort_values("profit_total_abs", ascending=False)
        fig = px.bar(
            chart_df,
            x="key",
            y="profit_total_abs",
            color="profit_total_abs",
            color_continuous_scale="RdYlGn",
            title="Pair Profit USDT",
            labels={"key": "Pair", "profit_total_abs": "Profit USDT"},
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No pair-level result found in the backtest zip.")

    left, right = st.columns(2)
    with left:
        st.markdown("**Long / Short Summary**")
        side_df = build_side_stats(trades_df)
        if side_df.empty:
            st.info("No trade-side data found.")
        else:
            st.dataframe(side_df, use_container_width=True, hide_index=True)
            side_fig = px.bar(
                side_df,
                x="Side",
                y="Profit USDT",
                color="Side",
                title="Long vs Short Profit",
            )
            st.plotly_chart(side_fig, use_container_width=True)

    with right:
        st.markdown("**Monthly Profit Heatmap**")
        monthly_rows = ((strategy.get("periodic_breakdown") or {}).get("month") or [])
        monthly_df = pd.DataFrame(monthly_rows)
        if monthly_df.empty:
            st.info("No monthly breakdown found.")
        else:
            monthly_df["date"] = pd.to_datetime(monthly_df["date_ts"], unit="ms", errors="coerce")
            monthly_df["year"] = monthly_df["date"].dt.year
            monthly_df["month"] = monthly_df["date"].dt.month
            starting_balance = safe_float(strategy.get("starting_balance"), 0) or 0
            monthly_df["profit_pct"] = (
                pd.to_numeric(monthly_df["profit_abs"], errors="coerce").fillna(0) / starting_balance * 100
                if starting_balance
                else 0
            )
            heatmap = monthly_df.pivot_table(index="year", columns="month", values="profit_pct", aggfunc="sum").fillna(0)
            heatmap = heatmap.reindex(columns=list(range(1, 13)), fill_value=0)
            heatmap.columns = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            fig = px.imshow(
                heatmap,
                aspect="auto",
                color_continuous_scale="RdYlGn",
                title="Monthly Profit % of Starting Balance",
                labels={"x": "Month", "y": "Year", "color": "Profit %"},
            )
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Per-pair Trade Count and Winrate**")
    pair_trade_df = build_pair_trade_stats(trades_df)
    if pair_trade_df.empty:
        st.info("No trade records found.")
    else:
        st.dataframe(pair_trade_df, use_container_width=True, hide_index=True)


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
        gate_rows = approval_summary_rows(approval_text)
        if gate_rows:
            st.dataframe(pd.DataFrame(gate_rows), use_container_width=True, hide_index=True)
        else:
            st.caption("Stable gate rules are unavailable because the latest approval report was not found.")
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
runtime_policy_data = load_json(RUNTIME_POLICY_REPORT)
project_roadmap_data = load_json(PROJECT_ROADMAP_REPORT)
runtime_summary = build_runtime_summary(
    stable_best_model_data,
    fast_best_model_data,
    stable_status_data,
    fast_status_data,
    evolution_status_data,
    autotune_status_data,
)

if approval_is_approved(approval_text) or has_approved_history(approved_history_data):
    render_metric_cards(backtest_data, daily_data, best_model_data)
else:
    st.info("Latest candidate did not pass the promotion gate. Live configuration remains on the last approved factor set.")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Live Factor Model", runtime_summary["live_model"])
    with col2:
        st.metric("Stable Model", runtime_summary["stable_model"])

overview_tab, decision_tab, backtest_tab, control_tab, schedule_tab, model_tab, history_tab, reports_tab = st.tabs(
    ["Overview", "Decision", "Backtest Detail", "Control Status", "Schedule", "Best Model", "History", "Reports"]
)

with overview_tab:
    render_runtime_summary(runtime_summary)
    st.divider()
    render_project_roadmap(project_roadmap_data)
    st.divider()
    render_approved_history(approved_history_data)
    st.divider()
    render_bucket_section(daily_data)
    st.divider()
    render_ranking_chart(daily_data)

with decision_tab:
    render_candidate_decision(backtest_data, approved_history_data, runtime_policy_data, approval_text)
    st.divider()
    render_data_quality(backtest_data, approval_text)
    st.divider()
    render_factor_health(best_model_data)

with backtest_tab:
    render_backtest_detail(backtest_data)

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

