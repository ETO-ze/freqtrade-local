import argparse
import json
import zipfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def atomic_write_json(path: Path, payload: Any) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    json.loads(text)
    atomic_write_text(path, text)


def load_backtest_strategy(zip_path: Path, strategy: str) -> dict[str, Any] | None:
    try:
        with zipfile.ZipFile(zip_path) as archive:
            json_names = [
                name
                for name in archive.namelist()
                if name.endswith(".json") and not name.endswith("_config.json")
            ]
            if not json_names:
                return None
            payload = json.loads(archive.read(json_names[0]).decode("utf-8"))
            return (payload.get("strategy") or {}).get(strategy)
    except Exception:
        return None


def score_pair(item: dict[str, float]) -> float:
    profit = item.get("profit_total_pct", 0.0)
    profit_factor = item.get("profit_factor", 0.0)
    winrate = item.get("winrate", 0.0)
    drawdown = item.get("max_drawdown_account", 0.0) * 100.0
    return round(profit + ((profit_factor - 1.0) * 8.0) + (winrate * 0.12) - (drawdown * 0.7), 4)


def suggested_action(score: float, trades: int, min_model_trades: int) -> str:
    if trades < min_model_trades:
        return "insufficient_data"
    if score >= 12:
        return "boost"
    if score >= 4:
        return "watch"
    return "reduce"


def analyze(freqtrade_root: Path, strategy: str, max_backtests: int, min_model_trades: int) -> dict[str, Any]:
    result_dir = freqtrade_root / "user_data" / "backtest_results"
    archives = sorted(result_dir.glob("backtest-result-*.zip"), key=lambda path: path.stat().st_mtime, reverse=True)
    archives = archives[: max(max_backtests, 1)]
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for archive in archives:
        strategy_payload = load_backtest_strategy(archive, strategy)
        if not strategy_payload:
            continue
        for pair_result in strategy_payload.get("results_per_pair") or []:
            pair = pair_result.get("key")
            if not pair or pair == "TOTAL":
                continue
            buckets[pair].append(pair_result)

    pairs: dict[str, dict[str, Any]] = {}
    for pair, items in buckets.items():
        trades = sum(int(item.get("trades") or 0) for item in items)
        if trades <= 0:
            continue
        profit_total_pct = sum(float(item.get("profit_total_pct") or 0.0) for item in items)
        weighted_winrate = sum(float(item.get("winrate") or 0.0) * int(item.get("trades") or 0) for item in items) / trades
        weighted_pf = sum(float(item.get("profit_factor") or 0.0) * int(item.get("trades") or 0) for item in items) / trades
        max_drawdown = max(float(item.get("max_drawdown_account") or 0.0) for item in items)
        aggregate = {
            "profit_total_pct": round(profit_total_pct, 4),
            "profit_factor": round(weighted_pf, 4),
            "winrate": round(weighted_winrate, 4),
            "max_drawdown_account": round(max_drawdown, 4),
        }
        feedback_score = score_pair(aggregate)
        pairs[pair] = {
            "feedback_score": feedback_score,
            "trades": trades,
            "winrate": round(weighted_winrate, 4),
            "profit_factor": round(weighted_pf, 4),
            "profit_total_pct": round(profit_total_pct, 4),
            "max_drawdown_pct": round(max_drawdown * 100.0, 4),
            "suggested_action": suggested_action(feedback_score, trades, min_model_trades),
        }

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "strategy": strategy,
        "source_backtests": len(archives),
        "min_model_trades": min_model_trades,
        "pairs": dict(sorted(pairs.items(), key=lambda item: item[1]["feedback_score"], reverse=True)),
    }


def write_report(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# OpenClaw Trade Feedback Isolated",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Strategy: {payload['strategy']}",
        f"- Source backtests: {payload['source_backtests']}",
        f"- Min model trades: {payload['min_model_trades']}",
        "",
        "## Pair Feedback",
        "",
        "| Pair | Score | Trades | Winrate | PF | Profit % | DD % | Action |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for pair, item in (payload.get("pairs") or {}).items():
        lines.append(
            f"| {pair} | {item['feedback_score']} | {item['trades']} | {item['winrate']} | "
            f"{item['profit_factor']} | {item['profit_total_pct']} | {item['max_drawdown_pct']} | "
            f"{item['suggested_action']} |"
        )
    atomic_write_text(path, "\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build isolated trade feedback from local backtest archives.")
    parser.add_argument("--freqtrade-root", required=True)
    parser.add_argument("--strategy", default="AlternativeHunter")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-report", required=True)
    parser.add_argument("--candidate-policy-json", required=True)
    parser.add_argument("--max-backtests", type=int, default=30)
    parser.add_argument("--min-model-trades", type=int, default=120)
    args = parser.parse_args()

    payload = analyze(Path(args.freqtrade_root), args.strategy, args.max_backtests, args.min_model_trades)
    output_json = Path(args.output_json)
    output_report = Path(args.output_report)
    candidate_policy = Path(args.candidate_policy_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_report.parent.mkdir(parents=True, exist_ok=True)
    candidate_policy.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(output_json, payload)
    atomic_write_json(candidate_policy, payload)
    write_report(output_report, payload)
    print(f"Wrote {output_json}")
    print(f"Wrote {output_report}")
    print(f"Wrote {candidate_policy}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
