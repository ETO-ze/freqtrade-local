import argparse
import json
import math
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd


def stem_to_pair(stem: str) -> str:
    parts = stem.split("_")
    if len(parts) < 3:
        raise ValueError(f"Unexpected market stem: {stem}")
    return f"{parts[0]}/{parts[1]}:{parts[2]}"


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def compute_volatility_score(realized_vol_5m: float) -> float:
    if not np.isfinite(realized_vol_5m) or realized_vol_5m <= 0:
        return 0.0
    target = 0.008
    tolerance = math.log(4.0)
    score = 1.0 - abs(math.log(realized_vol_5m) - math.log(target)) / tolerance
    return clamp(score)


def compute_persistence_score(quote_volume_24h: float, quote_volume_72h_avg: float) -> float:
    if quote_volume_72h_avg <= 0:
        return 0.0
    ratio = quote_volume_24h / quote_volume_72h_avg
    score = 1.0 - abs(ratio - 1.0) / 0.9
    return clamp(score)


def compute_stability_score(frame: pd.DataFrame, quote_volume_series: pd.Series) -> float:
    zero_volume_ratio = float((frame["volume"] <= 0).mean())
    dates = pd.to_datetime(frame["date"], utc=True)
    gap_ratio = float((dates.diff().dt.total_seconds().fillna(300.0) > 450.0).mean())
    mean_quote = float(quote_volume_series.mean()) if len(quote_volume_series) else 0.0
    std_quote = float(quote_volume_series.std()) if len(quote_volume_series) else 0.0
    cv = std_quote / mean_quote if mean_quote > 0 else 10.0
    penalty = min((zero_volume_ratio * 2.0) + (gap_ratio * 4.0) + max(cv - 2.0, 0.0) * 0.15, 1.0)
    return clamp(1.0 - penalty)


def compute_funding_score(funding_frame: pd.DataFrame | None) -> float:
    if funding_frame is None or funding_frame.empty:
        return 0.5
    recent = funding_frame.sort_values("date").tail(72)
    if recent.empty:
        return 0.5
    funding_series = recent["open"].astype(float)
    abs_mean = float(funding_series.abs().mean())
    std = float(funding_series.std())
    penalty = min((abs_mean * 800.0) + (std * 1200.0), 1.0)
    return clamp(1.0 - penalty)


def load_market_metrics(data_dir: Path, exclude_pairs: set[str], min_rows_72h: int) -> List[Dict]:
    metrics: List[Dict] = []
    for market_path in sorted(data_dir.glob("*-5m-futures.feather")):
        stem = market_path.name.replace("-5m-futures.feather", "")
        pair = stem_to_pair(stem)
        if pair in exclude_pairs:
            continue

        frame = pd.read_feather(market_path).sort_values("date").reset_index(drop=True)
        recent_72h = frame.tail(864).copy()
        if len(recent_72h) < min_rows_72h:
            continue

        recent_24h = recent_72h.tail(288).copy()
        quote_24 = (recent_24h["close"].astype(float) * recent_24h["volume"].astype(float))
        quote_72 = (recent_72h["close"].astype(float) * recent_72h["volume"].astype(float))
        quote_volume_24h = float(quote_24.sum())
        quote_volume_72h_avg = float(quote_72.sum() / max(len(recent_72h) / 288.0, 1.0))

        returns_24 = recent_24h["close"].astype(float).pct_change().dropna()
        realized_vol_5m = float(returns_24.std()) if not returns_24.empty else 0.0

        funding_path = data_dir / f"{stem}-1h-funding_rate.feather"
        funding_frame = pd.read_feather(funding_path) if funding_path.exists() else None

        metrics.append(
            {
                "pair": pair,
                "stem": stem,
                "rows_72h": int(len(recent_72h)),
                "last_timestamp": str(pd.to_datetime(recent_72h["date"].iloc[-1], utc=True)),
                "quote_volume_24h": round(quote_volume_24h, 2),
                "quote_volume_72h_avg": round(quote_volume_72h_avg, 2),
                "persistence_score": round(compute_persistence_score(quote_volume_24h, quote_volume_72h_avg), 4),
                "stability_score": round(compute_stability_score(recent_72h, quote_72), 4),
                "funding_score": round(compute_funding_score(funding_frame), 4),
                "volatility_score": round(compute_volatility_score(realized_vol_5m), 4),
                "realized_vol_5m": round(realized_vol_5m, 6),
            }
        )
    return metrics


def build_output(metrics: List[Dict], top_n: int) -> Dict:
    if not metrics:
        raise RuntimeError("No eligible pairs were found for the dynamic universe.")

    frame = pd.DataFrame(metrics)
    freshest = pd.to_datetime(frame["last_timestamp"], utc=True).max()
    recency_hours = (freshest - pd.to_datetime(frame["last_timestamp"], utc=True)).dt.total_seconds() / 3600.0
    frame["recency_score"] = recency_hours.apply(lambda hours: clamp(1.0 - (hours / 6.0)))
    frame["quote24_rank"] = frame["quote_volume_24h"].rank(method="average", pct=True)
    frame["quote72_rank"] = frame["quote_volume_72h_avg"].rank(method="average", pct=True)
    frame["overall_score"] = (
        frame["quote24_rank"] * 0.45
        + frame["quote72_rank"] * 0.20
        + frame["persistence_score"] * 0.10
        + frame["stability_score"] * 0.10
        + frame["funding_score"] * 0.10
        + frame["volatility_score"] * 0.03
        + frame["recency_score"] * 0.02
    ) * 100.0
    frame["overall_score"] = frame["overall_score"].round(2)

    ranked = frame.sort_values(
        ["overall_score", "quote_volume_24h", "quote_volume_72h_avg"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    selected = ranked.head(top_n).copy()

    return {
        "generated_at": pd.Timestamp.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "freshest_market_timestamp": str(freshest),
        "top_n": int(top_n),
        "selected_pairs": selected["pair"].tolist(),
        "ranking": ranked.to_dict(orient="records"),
    }


def write_markdown(path: Path, payload: Dict) -> None:
    lines = [
        "# OpenClaw Dynamic Alt Universe",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Freshest market timestamp: {payload['freshest_market_timestamp']}",
        f"- Selected count: {len(payload['selected_pairs'])}",
        "",
        "## Selected Pairs",
        "",
        ", ".join(payload["selected_pairs"]) if payload["selected_pairs"] else "none",
        "",
        "## Ranking",
        "",
        "| Pair | Score | Quote Vol 24h | Quote Vol 72h Avg | Persistence | Stability | Funding | Volatility | Recency |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in payload["ranking"]:
        lines.append(
            f"| {item['pair']} | {item['overall_score']} | {item['quote_volume_24h']} | "
            f"{item['quote_volume_72h_avg']} | {item['persistence_score']} | {item['stability_score']} | "
            f"{item['funding_score']} | {item['volatility_score']} | {round(float(item['recency_score']), 4)} |"
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a dynamic altcoin universe from local OKX futures data.")
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--base-config", required=True)
    parser.add_argument("--output-config", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--top-n", type=int, default=18)
    parser.add_argument("--exclude-pairs", default="BTC/USDT:USDT,ETH/USDT:USDT")
    parser.add_argument("--min-rows-72h", type=int, default=720)
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    base_config_path = Path(args.base_config)
    output_config_path = Path(args.output_config)
    output_json_path = Path(args.output_json)
    output_md_path = Path(args.output_md)
    exclude_pairs = {item.strip() for item in args.exclude_pairs.split(",") if item.strip()}

    metrics = load_market_metrics(data_dir, exclude_pairs, args.min_rows_72h)
    payload = build_output(metrics, args.top_n)

    base_config = json.loads(base_config_path.read_text(encoding="utf-8"))
    base_config["exchange"]["pair_whitelist"] = payload["selected_pairs"]

    output_config_path.parent.mkdir(parents=True, exist_ok=True)
    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    output_md_path.parent.mkdir(parents=True, exist_ok=True)

    output_config_path.write_text(json.dumps(base_config, indent=2), encoding="utf-8")
    output_json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_markdown(output_md_path, payload)
    print(f"Wrote {output_config_path}")
    print(f"Wrote {output_json_path}")
    print(f"Wrote {output_md_path}")


if __name__ == "__main__":
    main()
