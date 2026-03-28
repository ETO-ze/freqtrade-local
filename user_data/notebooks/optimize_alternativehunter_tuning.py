from __future__ import annotations

import argparse
import copy
import json
import random
import subprocess
import time
import zipfile
from pathlib import Path


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

SEARCH_SPACE = {
    "stake_weight": [0.6, 0.8, 1.0, 1.2, 1.4],
    "leverage_weight": [0.4, 0.6, 0.8, 1.0, 1.2],
    "same_side_recent_boost": [0.25, 0.4, 0.55, 0.7, 0.9],
    "same_side_bias_multiplier": [2.5, 3.0, 3.5, 4.0, 5.0],
    "opposite_side_penalty": [0.3, 0.4, 0.5, 0.6, 0.7],
    "opposite_side_recent_penalty": [0.1, 0.15, 0.2, 0.25, 0.3],
    "bias_block_threshold": [0.01, 0.012, 0.015, 0.018, 0.02],
    "recent_weight_block_threshold": [0.35, 0.4, 0.45, 0.5, 0.55],
    "minimum_side_multiplier": [0.05, 0.08, 0.1, 0.12, 0.15],
}


def load_json(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def select_pairs(policy: dict, max_pairs: int) -> list[str]:
    rows = []
    for pair, payload in (policy.get("pairs") or {}).items():
        decision = str(payload.get("decision", "") or "")
        if decision not in {"tradable", "observe"}:
            continue
        rows.append(
            (
                pair,
                1 if decision == "tradable" else 0,
                float(payload.get("recent_model_score", 0.0) or 0.0),
                float(payload.get("model_score", 0.0) or 0.0),
                float(payload.get("robust_score", 0.0) or 0.0),
            )
        )
    rows.sort(key=lambda item: (item[1], item[2], item[3], item[4]), reverse=True)
    return [pair for pair, *_ in rows[:max_pairs]]


def build_temp_config(base_config: dict, strategy: str, pairs: list[str], stake_amount: float, max_open_trades: int) -> dict:
    config = copy.deepcopy(base_config)
    config["bot_name"] = "freqtrade-autotune-alternativehunter"
    config["strategy"] = strategy
    config["stake_amount"] = float(stake_amount)
    config["max_open_trades"] = int(max_open_trades)
    config["exchange"]["pair_whitelist"] = pairs
    return config


def latest_backtest_zip(backtest_root: Path) -> Path | None:
    files = sorted(backtest_root.glob("backtest-result-*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def parse_backtest(zip_path: Path, strategy_name: str) -> dict:
    with zipfile.ZipFile(zip_path) as zf:
        json_name = [name for name in zf.namelist() if name.endswith(".json") and "_config" not in name][0]
        payload = json.loads(zf.read(json_name).decode("utf-8"))
    data = payload["strategy"][strategy_name]
    return {
        "total_profit_pct": round(float(data["profit_total"]) * 100.0, 2),
        "profit_factor": round(float(data["profit_factor"]), 4),
        "winrate": round(float(data["winrate"]) * 100.0, 2),
        "max_drawdown_pct": round(float(data["max_drawdown_account"]) * 100.0, 2),
        "trade_count": int(data["total_trades"]),
        "profit_long_pct": round(float(data["profit_total_long"]) * 100.0, 2),
        "profit_short_pct": round(float(data["profit_total_short"]) * 100.0, 2),
        "final_balance": round(float(data["final_balance"]), 3),
    }


def score_metrics(metrics: dict, thresholds: dict) -> tuple[bool, float]:
    approved = (
        metrics["total_profit_pct"] >= thresholds["min_profit_pct"]
        and metrics["profit_factor"] >= thresholds["min_profit_factor"]
        and metrics["winrate"] >= thresholds["min_winrate_pct"]
        and metrics["max_drawdown_pct"] <= thresholds["max_drawdown_pct"]
        and metrics["trade_count"] >= thresholds["min_trades"]
    )
    score = (
        metrics["total_profit_pct"] * 4.0
        + metrics["profit_factor"] * 25.0
        + metrics["winrate"] * 0.18
        - metrics["max_drawdown_pct"] * 1.8
        + min(metrics["trade_count"], 400) * 0.03
    )
    if not approved:
        score -= 50.0
    return approved, round(score, 4)


def candidate_tunings(base_tuning: dict, trials: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    candidates = [dict(base_tuning)]
    while len(candidates) < trials:
        candidate = {}
        for key, values in SEARCH_SPACE.items():
            if rng.random() < 0.35:
                candidate[key] = base_tuning.get(key, DEFAULT_TUNING[key])
            else:
                candidate[key] = rng.choice(values)
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


def run_trial(
    freqtrade_root: Path,
    strategy_name: str,
    base_config: dict,
    policy: dict,
    tuning: dict,
    timerange: str,
    pairs: list[str],
    stake_amount: float,
    max_open_trades: int,
) -> tuple[dict, Path]:
    user_data = freqtrade_root / "user_data"
    backtest_root = user_data / "backtest_results"
    before = latest_backtest_zip(backtest_root)
    ts = int(time.time() * 1000)
    config_path = user_data / f"config.autotune.{ts}.json"
    policy_path = user_data / f"model_runtime_policy.autotune.{ts}.json"

    try:
        save_json(config_path, build_temp_config(base_config, strategy_name, pairs, stake_amount, max_open_trades))
        temp_policy = copy.deepcopy(policy)
        temp_policy["tuning"] = tuning
        save_json(policy_path, temp_policy)

        command = [
            "docker",
            "run",
            "--rm",
            "-e",
            "FT_RUNTIME_POLICY_PATH=/freqtrade/user_data/" + policy_path.name,
            "-v",
            f"{user_data}:/freqtrade/user_data",
            "freqtradeorg/freqtrade:stable",
            "backtesting",
            "--config",
            "/freqtrade/user_data/" + config_path.name,
            "--strategy",
            strategy_name,
            "--timerange",
            timerange,
            "--export",
            "trades",
        ]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=freqtrade_root,
        )
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "").strip())

        after = latest_backtest_zip(backtest_root)
        if not after or (before and after == before):
            raise RuntimeError("Backtest result zip not updated.")

        return parse_backtest(after, strategy_name), after
    finally:
        if config_path.exists():
            config_path.unlink()
        if policy_path.exists():
            policy_path.unlink()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freqtrade-root", required=True)
    parser.add_argument("--runtime-policy", required=True)
    parser.add_argument("--base-config", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--approved-tuning", required=True)
    parser.add_argument("--strategy", default="AlternativeHunter")
    parser.add_argument("--timerange", default="20251201-20260318")
    parser.add_argument("--trials", type=int, default=8)
    parser.add_argument("--max-pairs", type=int, default=10)
    parser.add_argument("--stake-amount", type=float, default=50.0)
    parser.add_argument("--max-open-trades", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-profit-pct", type=float, default=10.0)
    parser.add_argument("--min-profit-factor", type=float, default=1.5)
    parser.add_argument("--min-winrate-pct", type=float, default=60.0)
    parser.add_argument("--max-drawdown-pct", type=float, default=12.0)
    parser.add_argument("--min-trades", type=int, default=240)
    args = parser.parse_args()

    freqtrade_root = Path(args.freqtrade_root)
    runtime_policy_path = Path(args.runtime_policy)
    base_config_path = Path(args.base_config)
    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    approved_tuning_path = Path(args.approved_tuning)

    policy = load_json(runtime_policy_path)
    if not isinstance(policy, dict):
        raise RuntimeError(f"Runtime policy not found: {runtime_policy_path}")
    base_config = load_json(base_config_path)
    if not isinstance(base_config, dict):
        raise RuntimeError(f"Base config not found: {base_config_path}")

    pairs = select_pairs(policy, args.max_pairs)
    if not pairs:
        raise RuntimeError("No tradable pairs available for auto-tuning.")

    current_approved = load_json(approved_tuning_path)
    base_tuning = dict(DEFAULT_TUNING)
    if isinstance(current_approved, dict) and isinstance(current_approved.get("tuning"), dict):
        base_tuning.update(current_approved["tuning"])
    elif isinstance(policy.get("tuning"), dict):
        base_tuning.update(policy["tuning"])

    thresholds = {
        "min_profit_pct": args.min_profit_pct,
        "min_profit_factor": args.min_profit_factor,
        "min_winrate_pct": args.min_winrate_pct,
        "max_drawdown_pct": args.max_drawdown_pct,
        "min_trades": args.min_trades,
    }

    results = []
    best = None
    for idx, tuning in enumerate(candidate_tunings(base_tuning, args.trials, args.seed), start=1):
        metrics, zip_path = run_trial(
            freqtrade_root=freqtrade_root,
            strategy_name=args.strategy,
            base_config=base_config,
            policy=policy,
            tuning=tuning,
            timerange=args.timerange,
            pairs=pairs,
            stake_amount=args.stake_amount,
            max_open_trades=args.max_open_trades,
        )
        approved, objective = score_metrics(metrics, thresholds)
        entry = {
            "trial": idx,
            "approved": approved,
            "objective": objective,
            "tuning": tuning,
            "metrics": metrics,
            "result_zip": str(zip_path),
        }
        results.append(entry)
        if best is None or entry["objective"] > best["objective"]:
            best = entry

    output = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "strategy": args.strategy,
        "runtime_policy": str(runtime_policy_path),
        "base_config": str(base_config_path),
        "pairs": pairs,
        "thresholds": thresholds,
        "best": best,
        "results": results,
    }
    save_json(output_json, output)

    lines = [
        "# AlternativeHunter Auto Tune",
        "",
        f"- Generated: {output['generated_at']}",
        f"- Strategy: {args.strategy}",
        f"- Pairs: {', '.join(pairs)}",
        f"- Trials: {args.trials}",
        "",
        "## Best Candidate",
        "",
        f"- Approved: {best['approved']}",
        f"- Objective: {best['objective']}",
        f"- Profit: {best['metrics']['total_profit_pct']}%",
        f"- Profit Factor: {best['metrics']['profit_factor']}",
        f"- Winrate: {best['metrics']['winrate']}%",
        f"- Drawdown: {best['metrics']['max_drawdown_pct']}%",
        f"- Trades: {best['metrics']['trade_count']}",
        f"- Result zip: {best['result_zip']}",
        "",
        "## Best Tuning",
        "",
        "```json",
        json.dumps(best["tuning"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Trial Summary",
        "",
        "| Trial | Approved | Objective | Profit % | PF | Winrate % | Drawdown % | Trades |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in results:
        m = item["metrics"]
        lines.append(
            f"| {item['trial']} | {item['approved']} | {item['objective']} | {m['total_profit_pct']} | {m['profit_factor']} | {m['winrate']} | {m['max_drawdown_pct']} | {m['trade_count']} |"
        )
    output_md.write_text("\n".join(lines), encoding="utf-8")

    current_score = None
    if isinstance(current_approved, dict):
        current_score = float(current_approved.get("objective", -1e9))

    if best["approved"] and (current_score is None or best["objective"] >= current_score):
        approved_payload = {
            "generated_at": output["generated_at"],
            "strategy": args.strategy,
            "objective": best["objective"],
            "pairs": pairs,
            "metrics": best["metrics"],
            "tuning": best["tuning"],
            "result_zip": best["result_zip"],
        }
        save_json(approved_tuning_path, approved_payload)


if __name__ == "__main__":
    main()
