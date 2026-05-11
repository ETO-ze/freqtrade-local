import argparse
import json
import math
import zipfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, "", "N/A", "n/a"):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def load_strategy_payload(zip_path: Path, strategy_name: str) -> dict[str, Any]:
    with zipfile.ZipFile(zip_path) as zf:
        json_names = [name for name in zf.namelist() if name.endswith(".json") and "_config" not in name]
        if not json_names:
            raise FileNotFoundError(f"No backtest result json found in {zip_path}")
        payload = json.loads(zf.read(json_names[0]).decode("utf-8"))
    strategy = payload.get("strategy") or {}
    if strategy_name in strategy:
        return strategy[strategy_name]
    if strategy:
        return next(iter(strategy.values()))
    raise KeyError(f"No strategy payload found in {zip_path}")


def month_key(date_text: str) -> str:
    return date_text[:7]


def parse_trade_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def parse_days(duration_text: str) -> float:
    if not duration_text:
        return 0.0
    text = str(duration_text)
    if "day" in text:
        try:
            return float(text.split("day")[0].strip())
        except ValueError:
            return 0.0
    return 0.0


def profit_factor_for(profits: list[float]) -> float:
    gross_profit = sum(value for value in profits if value > 0)
    gross_loss = abs(sum(value for value in profits if value < 0))
    if gross_loss == 0:
        return 99.0 if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def build_segments(trades: list[dict[str, Any]], starting_balance: float, generated_at: datetime) -> dict[str, Any]:
    definitions = [
        ("train_proxy_2025_01_2025_09", datetime(2025, 1, 1, tzinfo=timezone.utc), datetime(2025, 10, 1, tzinfo=timezone.utc)),
        ("validation_proxy_2025_10_2026_01", datetime(2025, 10, 1, tzinfo=timezone.utc), datetime(2026, 2, 1, tzinfo=timezone.utc)),
        ("test_proxy_2026_02_now", datetime(2026, 2, 1, tzinfo=timezone.utc), generated_at + timedelta(days=1)),
        ("recent_120d", generated_at - timedelta(days=120), generated_at + timedelta(days=1)),
        ("recent_60d", generated_at - timedelta(days=60), generated_at + timedelta(days=1)),
    ]
    rows = {}
    segment_scores = []
    hard_blocks = []
    for name, start, end in definitions:
        segment_trades = []
        for trade in trades:
            close_date = parse_trade_datetime(trade.get("close_date") or trade.get("open_date"))
            if close_date is not None and start <= close_date < end:
                segment_trades.append(trade)

        profits = [safe_float(trade.get("profit_abs")) for trade in segment_trades]
        profit_abs = sum(profits)
        profit_pct = (profit_abs / starting_balance * 100.0) if starting_balance > 0 else 0.0
        wins = sum(1 for value in profits if value > 0)
        trade_count = len(segment_trades)
        winrate = (wins / trade_count * 100.0) if trade_count else 0.0
        pf = profit_factor_for(profits)
        pair_profit: dict[str, float] = defaultdict(float)
        for trade, profit in zip(segment_trades, profits):
            pair_profit[str(trade.get("pair") or "unknown")] += profit
        gross_positive = sum(value for value in pair_profit.values() if value > 0)
        top_pair_share = (max(pair_profit.values()) / gross_positive) if gross_positive > 0 and pair_profit else 0.0

        if trade_count == 0:
            score = 0.0
        else:
            score = 50.0
            score += min(max(profit_pct, -25.0), 80.0) * 0.45
            score += min(max(pf - 1.0, -1.0), 3.0) * 10.0
            score += min(max(winrate - 50.0, -30.0), 35.0) * 0.35
            score -= max(top_pair_share - 0.55, 0.0) * 35.0
            score = round(max(0.0, min(100.0, score)), 2)
            segment_scores.append(score)

        rows[name] = {
            "start": start.strftime("%Y-%m-%d"),
            "end": (end - timedelta(days=1)).strftime("%Y-%m-%d"),
            "profit_pct": round(profit_pct, 4),
            "profit_abs": round(profit_abs, 6),
            "trade_count": trade_count,
            "winrate": round(winrate, 4),
            "profit_factor": round(pf, 4),
            "top_pair_share": round(top_pair_share, 4),
            "score": score,
        }

    validation = rows["validation_proxy_2025_10_2026_01"]
    test = rows["test_proxy_2026_02_now"]
    recent_60 = rows["recent_60d"]
    if validation["trade_count"] >= 40 and test["trade_count"] >= 40 and validation["profit_pct"] < -10 and test["profit_pct"] < -10:
        hard_blocks.append("validation_and_test_both_negative")
    if test["trade_count"] >= 50 and test["profit_pct"] < -20:
        hard_blocks.append("test_segment_loss_above_limit")
    if recent_60["trade_count"] >= 20 and recent_60["profit_pct"] < -18:
        hard_blocks.append("recent_60d_loss_above_limit")

    average_score = round(sum(segment_scores) / len(segment_scores), 2) if segment_scores else 0.0
    positive_core_segments = sum(
        1
        for key in ("validation_proxy_2025_10_2026_01", "test_proxy_2026_02_now", "recent_120d", "recent_60d")
        if rows[key]["trade_count"] > 0 and rows[key]["profit_pct"] > 0
    )
    return {
        "score": average_score,
        "positive_core_segments": positive_core_segments,
        "hard_blocks": hard_blocks,
        "segments": rows,
    }


def evaluate(strategy: dict[str, Any]) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc)
    starting_balance = safe_float(strategy.get("starting_balance"), 1000.0)
    total_profit_abs = safe_float(strategy.get("profit_total_abs"))
    total_profit_pct = safe_float(strategy.get("profit_total")) * 100.0
    max_drawdown_pct = safe_float(strategy.get("max_drawdown_account")) * 100.0
    trades = strategy.get("trades") or []

    monthly_profit: dict[str, float] = defaultdict(float)
    pair_profit: dict[str, float] = defaultdict(float)
    pair_trades: dict[str, int] = defaultdict(int)
    gross_positive = 0.0
    long_profit = 0.0
    short_profit = 0.0
    long_trades = 0
    short_trades = 0

    typed_trades = [trade for trade in trades if isinstance(trade, dict)]
    for trade in typed_trades:
        close_date = str(trade.get("close_date") or trade.get("open_date") or "")
        profit_abs = safe_float(trade.get("profit_abs"))
        pair = str(trade.get("pair") or "unknown")
        monthly_profit[month_key(close_date)] += profit_abs
        pair_profit[pair] += profit_abs
        pair_trades[pair] += 1
        if profit_abs > 0:
            gross_positive += profit_abs
        if trade.get("is_short"):
            short_profit += profit_abs
            short_trades += 1
        else:
            long_profit += profit_abs
            long_trades += 1

    month_returns = [
        (profit / starting_balance * 100.0) if starting_balance > 0 else 0.0
        for _, profit in sorted(monthly_profit.items())
    ]
    profitable_months = sum(1 for value in month_returns if value > 0)
    month_count = len(month_returns)
    profitable_month_ratio = profitable_months / month_count if month_count else 0.0
    worst_month_pct = min(month_returns) if month_returns else 0.0
    best_month_pct = max(month_returns) if month_returns else 0.0
    month_std = 0.0
    if month_count > 1:
        mean = sum(month_returns) / month_count
        month_std = math.sqrt(sum((value - mean) ** 2 for value in month_returns) / (month_count - 1))

    top_pair = max(pair_profit.items(), key=lambda item: item[1]) if pair_profit else ("", 0.0)
    top_positive_pair_share = (max(pair_profit.values()) / gross_positive) if gross_positive > 0 and pair_profit else 0.0
    top_trade_share = (max(pair_trades.values()) / len(trades)) if trades and pair_trades else 0.0
    side_profit_total = abs(long_profit) + abs(short_profit)
    side_imbalance = abs(long_profit - short_profit) / side_profit_total if side_profit_total > 0 else 0.0
    drawdown_days = parse_days(strategy.get("drawdown_duration") or "")

    walk_forward = build_segments(typed_trades, starting_balance, generated_at)

    score = 100.0
    score -= max(max_drawdown_pct - 18.0, 0.0) * 1.2
    score -= max(abs(worst_month_pct) - 12.0, 0.0) * 1.1
    score -= max(top_positive_pair_share - 0.45, 0.0) * 55.0
    score -= max(top_trade_share - 0.35, 0.0) * 35.0
    score -= max(0.45 - profitable_month_ratio, 0.0) * 45.0
    score -= max(drawdown_days - 120.0, 0.0) * 0.08
    score -= max(month_std - 18.0, 0.0) * 0.45
    score += min(max(walk_forward["score"] - 50.0, -35.0), 35.0) * 0.25
    score += max(walk_forward["positive_core_segments"] - 2, 0) * 2.5
    score = round(max(0.0, min(100.0, score)), 2)

    hard_blocks = []
    if top_positive_pair_share > 0.82 and total_profit_pct < 160.0:
        hard_blocks.append("single_pair_profit_concentration")
    if profitable_month_ratio < 0.30 and total_profit_pct < 120.0:
        hard_blocks.append("too_few_profitable_months")
    if max_drawdown_pct > 45.0:
        hard_blocks.append("drawdown_above_safety_limit")
    if worst_month_pct < -45.0:
        hard_blocks.append("worst_month_above_safety_limit")
    hard_blocks.extend(walk_forward["hard_blocks"])

    return {
        "generated_at": generated_at.astimezone().strftime("%Y-%m-%d %H:%M:%S"),
        "score": score,
        "passed": score >= 45.0 and not hard_blocks,
        "hard_blocks": hard_blocks,
        "walk_forward": walk_forward,
        "summary": {
            "total_profit_pct": round(total_profit_pct, 4),
            "total_profit_abs": round(total_profit_abs, 6),
            "max_drawdown_pct": round(max_drawdown_pct, 4),
            "trade_count": len(trades),
            "month_count": month_count,
            "profitable_month_ratio": round(profitable_month_ratio, 4),
            "worst_month_pct": round(worst_month_pct, 4),
            "best_month_pct": round(best_month_pct, 4),
            "monthly_return_std": round(month_std, 4),
            "top_pair": top_pair[0],
            "top_pair_profit_abs": round(top_pair[1], 6),
            "top_positive_pair_share": round(top_positive_pair_share, 4),
            "top_trade_share": round(top_trade_share, 4),
            "long_profit_abs": round(long_profit, 6),
            "short_profit_abs": round(short_profit, 6),
            "long_trades": long_trades,
            "short_trades": short_trades,
            "side_imbalance": round(side_imbalance, 4),
            "drawdown_duration_days": round(drawdown_days, 2),
        },
    }


def write_report(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# OpenClaw Backtest Stability",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Score: {payload['score']}",
        f"- Passed: {payload['passed']}",
        f"- Hard blocks: {', '.join(payload['hard_blocks']) if payload['hard_blocks'] else 'none'}",
        "",
        "## Summary",
        "",
    ]
    for key, value in summary.items():
        lines.append(f"- {key}: {value}")
    walk_forward = payload.get("walk_forward") or {}
    if walk_forward:
        lines.extend(
            [
                "",
                "## Segmented / Walk-Forward Proxy",
                "",
                f"- Score: {walk_forward.get('score')}",
                f"- Positive core segments: {walk_forward.get('positive_core_segments')}",
                f"- Hard blocks: {', '.join(walk_forward.get('hard_blocks') or []) if walk_forward.get('hard_blocks') else 'none'}",
                "",
                "| Segment | Start | End | Profit % | PF | Winrate % | Trades | Top Pair Share | Score |",
                "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for name, row in (walk_forward.get("segments") or {}).items():
            lines.append(
                f"| {name} | {row.get('start')} | {row.get('end')} | {row.get('profit_pct')} | "
                f"{row.get('profit_factor')} | {row.get('winrate')} | {row.get('trade_count')} | "
                f"{row.get('top_pair_share')} | {row.get('score')} |"
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate backtest stability for OpenClaw promotion gates.")
    parser.add_argument("--zip", required=True)
    parser.add_argument("--strategy", default="AlternativeHunter")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    zip_path = Path(args.zip)
    payload = evaluate(load_strategy_payload(zip_path, args.strategy))
    payload["source_zip"] = str(zip_path)
    output_json = Path(args.output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(Path(args.output_md), payload)
    print(f"Wrote {output_json}")
    print(f"Wrote {args.output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

