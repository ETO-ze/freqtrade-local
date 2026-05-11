import argparse
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd


DEFAULT_DENY_SYMBOLS = {
    "USDT",
    "USDC",
    "FDUSD",
    "TUSD",
    "DAI",
    "USD",
    "USDE",
    "WBTC",
    "WETH",
    "STETH",
    "WEETH",
    "BETH",
    "USTC",
    "LUNC",
}


def stem_to_pair(stem: str) -> str:
    parts = stem.split("_")
    if len(parts) < 3:
        raise ValueError(f"Unexpected market stem: {stem}")
    return f"{parts[0]}/{parts[1]}:{parts[2]}"


def pair_to_symbol(pair: str) -> str:
    return pair.split("/")[0].strip().upper()


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


def compute_time_series_confirmation(close: pd.Series, realized_vol_5m: float) -> Dict:
    if close.empty or len(close) < 72:
        return {
            "trend_confirmation_score": 0.0,
            "trend_direction_score": 0.0,
            "ema_stack_score": 0.0,
            "breakout_score": 0.0,
            "trend_consistency_score": 0.0,
        }

    close = close.astype(float)
    last = float(close.iloc[-1])
    if last <= 0:
        return {
            "trend_confirmation_score": 0.0,
            "trend_direction_score": 0.0,
            "ema_stack_score": 0.0,
            "breakout_score": 0.0,
            "trend_consistency_score": 0.0,
        }

    ema_fast = close.ewm(span=12, adjust=False).mean()
    ema_mid = close.ewm(span=48, adjust=False).mean()
    ema_slow = close.ewm(span=144, adjust=False).mean()
    fast_last = float(ema_fast.iloc[-1])
    mid_last = float(ema_mid.iloc[-1])
    slow_last = float(ema_slow.iloc[-1])

    bullish_stack = fast_last > mid_last > slow_last
    bearish_stack = fast_last < mid_last < slow_last
    ema_spread = abs(fast_last / slow_last - 1.0) if slow_last > 0 else 0.0
    ema_stack_score = clamp(0.35 + min(ema_spread / 0.035, 0.65)) if bullish_stack or bearish_stack else clamp(ema_spread / 0.05)

    high_72 = float(close.tail(864).max())
    low_72 = float(close.tail(864).min())
    breakout_up = (last / high_72) if high_72 > 0 else 0.0
    breakout_down = (low_72 / last) if last > 0 else 0.0
    breakout_score = clamp(max(breakout_up, breakout_down) - 0.92, 0.0, 0.08) / 0.08

    tail = close.tail(96)
    mid_tail = ema_mid.tail(len(tail))
    above_mid = float((tail > mid_tail).mean()) if len(tail) else 0.0
    below_mid = float((tail < mid_tail).mean()) if len(tail) else 0.0
    trend_consistency_score = max(above_mid, below_mid)

    ret_24h = float(last / float(close.iloc[-289]) - 1.0) if len(close) >= 289 and close.iloc[-289] > 0 else 0.0
    ret_72h = float(last / float(close.iloc[0]) - 1.0) if close.iloc[0] > 0 else 0.0
    raw_direction = (ret_24h * 2.5) + (ret_72h * 1.2) + ((fast_last / mid_last - 1.0) * 2.0 if mid_last > 0 else 0.0)
    trend_direction_score = clamp(raw_direction / 0.16, -1.0, 1.0)

    vol_penalty = 0.0
    if np.isfinite(realized_vol_5m) and realized_vol_5m > 0.018:
        vol_penalty = min((realized_vol_5m - 0.018) / 0.018, 0.35)
    confirmation = (
        ema_stack_score * 0.35
        + breakout_score * 0.20
        + trend_consistency_score * 0.25
        + abs(trend_direction_score) * 0.20
    )
    confirmation = clamp(confirmation - vol_penalty)

    return {
        "trend_confirmation_score": round(confirmation, 4),
        "trend_direction_score": round(trend_direction_score, 4),
        "ema_stack_score": round(ema_stack_score, 4),
        "breakout_score": round(breakout_score, 4),
        "trend_consistency_score": round(trend_consistency_score, 4),
    }


def load_json_cache(path: Path, max_age_hours: float) -> List[Dict] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        fetched_at = float(payload.get("fetched_at_epoch", 0.0) or 0.0)
        if max_age_hours > 0 and time.time() - fetched_at > max_age_hours * 3600.0:
            return None
        records = payload.get("records")
        return records if isinstance(records, list) else None
    except Exception:
        return None


def write_json_cache(path: Path, records: List[Dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at_epoch": time.time(),
        "fetched_at": pd.Timestamp.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "records": records,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def fetch_coingecko_markets(
    cache_path: Path,
    pages: int,
    per_page: int,
    timeout_seconds: int,
    cache_max_age_hours: float,
) -> tuple[List[Dict], str]:
    cached = load_json_cache(cache_path, cache_max_age_hours)
    expected_records = max(1, pages) * max(1, min(per_page, 250))
    if cached is not None and len(cached) >= expected_records:
        return cached, "cache"

    records: List[Dict] = []
    base_url = "https://api.coingecko.com/api/v3/coins/markets"
    for page in range(1, max(1, pages) + 1):
        query = urllib.parse.urlencode(
            {
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": max(1, min(per_page, 250)),
                "page": page,
                "sparkline": "false",
                "locale": "en",
            }
        )
        request = urllib.request.Request(
            f"{base_url}?{query}",
            headers={"User-Agent": "OpenClaw-Freqtrade/1.0"},
        )
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            chunk = json.loads(response.read().decode("utf-8"))
            if not isinstance(chunk, list) or not chunk:
                break
            records.extend(chunk)

    if records:
        write_json_cache(cache_path, records)
    return records, "coingecko"


def build_market_cap_by_symbol(records: List[Dict]) -> Dict[str, Dict]:
    by_symbol: Dict[str, Dict] = {}
    for record in records:
        symbol = str(record.get("symbol", "") or "").upper()
        if not symbol:
            continue
        market_cap = float(record.get("market_cap") or 0.0)
        current = by_symbol.get(symbol)
        if current is None or market_cap > float(current.get("market_cap") or 0.0):
            by_symbol[symbol] = record
    return by_symbol


def enrich_with_market_cap_filter(
    metrics: List[Dict],
    records: List[Dict],
    source: str,
    require_market_cap: bool,
    market_cap_top_n: int,
    min_market_cap_usd: float,
    min_market_volume_usd: float,
    max_volume_to_market_cap_ratio: float,
    deny_symbols: set[str],
) -> tuple[List[Dict], Dict]:
    by_symbol = build_market_cap_by_symbol(records)
    kept: List[Dict] = []
    stats = {
        "source": source,
        "require_market_cap": bool(require_market_cap),
        "records": len(records),
        "matched": 0,
        "excluded_deny_symbol": 0,
        "excluded_missing_market_cap": 0,
        "excluded_market_cap_rank": 0,
        "excluded_market_cap_floor": 0,
        "excluded_market_volume_floor": 0,
        "excluded_turnover_proxy": 0,
    }

    for item in metrics:
        symbol = pair_to_symbol(item["pair"])
        if symbol in deny_symbols:
            stats["excluded_deny_symbol"] += 1
            continue

        enriched = dict(item)
        market = by_symbol.get(symbol)
        if not market:
            enriched.update(
                {
                    "market_cap_matched": False,
                    "market_cap_source": source,
                    "market_cap_rank": None,
                    "market_cap_usd": None,
                    "market_volume_usd": None,
                    "market_turnover_ratio": None,
                    "coingecko_id": "",
                    "market_cap_score": 0.0,
                }
            )
            if require_market_cap:
                stats["excluded_missing_market_cap"] += 1
                continue
            kept.append(enriched)
            continue

        rank = int(market.get("market_cap_rank") or 999999)
        market_cap = float(market.get("market_cap") or 0.0)
        market_volume = float(market.get("total_volume") or 0.0)
        turnover_ratio = market_volume / market_cap if market_cap > 0 else 999.0

        if market_cap_top_n > 0 and rank > market_cap_top_n:
            stats["excluded_market_cap_rank"] += 1
            continue
        if min_market_cap_usd > 0 and market_cap < min_market_cap_usd:
            stats["excluded_market_cap_floor"] += 1
            continue
        if min_market_volume_usd > 0 and market_volume < min_market_volume_usd:
            stats["excluded_market_volume_floor"] += 1
            continue
        if max_volume_to_market_cap_ratio > 0 and turnover_ratio > max_volume_to_market_cap_ratio:
            stats["excluded_turnover_proxy"] += 1
            continue

        stats["matched"] += 1
        score_rank = clamp(1.0 - ((rank - 1.0) / max(float(market_cap_top_n or 250), 1.0)))
        enriched.update(
            {
                "market_cap_matched": True,
                "market_cap_source": source,
                "market_cap_rank": rank,
                "market_cap_usd": round(market_cap, 2),
                "market_volume_usd": round(market_volume, 2),
                "market_turnover_ratio": round(turnover_ratio, 4),
                "coingecko_id": str(market.get("id", "") or ""),
                "market_cap_score": round(score_rank, 4),
            }
        )
        kept.append(enriched)

    return kept, stats


def load_ohlcv_frame(data_dir: Path, symbol: str, timeframe: str = "1h") -> pd.DataFrame | None:
    path = data_dir / f"{symbol}_USDT_USDT-{timeframe}-futures.feather"
    if not path.exists():
        return None
    try:
        frame = pd.read_feather(path).sort_values("date").reset_index(drop=True)
        return frame if not frame.empty else None
    except Exception:
        return None


def benchmark_signal(frame: pd.DataFrame | None, symbol: str) -> Dict:
    if frame is None or len(frame) < 36:
        return {"symbol": symbol, "available": False}
    close = frame["close"].astype(float)
    last = float(close.iloc[-1])
    ret_24h = float(last / float(close.iloc[-25]) - 1.0) if len(close) >= 25 and close.iloc[-25] > 0 else 0.0
    ret_72h = float(last / float(close.iloc[-73]) - 1.0) if len(close) >= 73 and close.iloc[-73] > 0 else ret_24h
    ma_72 = float(close.tail(min(72, len(close))).mean())
    ma_gap = (last / ma_72 - 1.0) if ma_72 > 0 else 0.0
    hourly_vol = float(close.pct_change().tail(min(72, len(close))).std() or 0.0)
    raw_score = (ret_24h * 3.0) + (ret_72h * 1.5) + (ma_gap * 2.0)
    normalized = clamp(raw_score / 0.12, -1.0, 1.0)
    if normalized >= 0.35:
        trend = "up"
    elif normalized <= -0.35:
        trend = "down"
    else:
        trend = "flat"
    return {
        "symbol": symbol,
        "available": True,
        "last_timestamp": str(pd.to_datetime(frame["date"].iloc[-1], utc=True)),
        "ret_24h": round(ret_24h, 5),
        "ret_72h": round(ret_72h, 5),
        "ma_gap_72h": round(ma_gap, 5),
        "hourly_vol_72h": round(hourly_vol, 6),
        "trend_score": round(normalized, 4),
        "trend": trend,
    }


def build_benchmark_regime(data_dir: Path) -> Dict:
    btc = benchmark_signal(load_ohlcv_frame(data_dir, "BTC"), "BTC")
    eth = benchmark_signal(load_ohlcv_frame(data_dir, "ETH"), "ETH")
    available_scores = [float(x["trend_score"]) for x in (btc, eth) if x.get("available")]
    available_vols = [float(x["hourly_vol_72h"]) for x in (btc, eth) if x.get("available")]
    combined = float(np.mean(available_scores)) if available_scores else 0.0
    combined_vol = float(np.mean(available_vols)) if available_vols else 0.0
    if combined >= 0.35:
        regime = "risk_on"
        risk_scale = 1.15
        leverage_scale = 1.10
    elif combined <= -0.35:
        regime = "risk_off"
        risk_scale = 0.65
        leverage_scale = 0.70
    else:
        regime = "neutral"
        risk_scale = 1.0
        leverage_scale = 1.0
    if combined_vol >= 0.018:
        volatility_state = "high"
        risk_scale *= 0.72
        leverage_scale *= 0.72
    elif combined_vol <= 0.006:
        volatility_state = "low"
        risk_scale *= 1.04
        leverage_scale *= 1.03
    else:
        volatility_state = "normal"
    return {
        "regime": regime,
        "combined_trend_score": round(combined, 4),
        "combined_hourly_vol_72h": round(combined_vol, 6),
        "volatility_state": volatility_state,
        "risk_scale": round(risk_scale, 4),
        "leverage_scale": round(leverage_scale, 4),
        "btc": btc,
        "eth": eth,
    }


def load_market_metrics(data_dir: Path, exclude_pairs: set[str], min_rows_72h: int, min_history_days: float) -> List[Dict]:
    metrics: List[Dict] = []
    for market_path in sorted(data_dir.glob("*-5m-futures.feather")):
        stem = market_path.name.replace("-5m-futures.feather", "")
        pair = stem_to_pair(stem)
        if pair in exclude_pairs:
            continue

        frame = pd.read_feather(market_path).sort_values("date").reset_index(drop=True)
        dates_all = pd.to_datetime(frame["date"], utc=True)
        history_days = float((dates_all.iloc[-1] - dates_all.iloc[0]).total_seconds() / 86400.0) if len(dates_all) else 0.0
        if min_history_days > 0 and history_days < min_history_days:
            continue

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
        close_72 = recent_72h["close"].astype(float)
        last_close = float(close_72.iloc[-1])
        price_ret_24h = float(last_close / float(recent_24h["close"].astype(float).iloc[0]) - 1.0) if len(recent_24h) > 1 and float(recent_24h["close"].iloc[0]) > 0 else 0.0
        price_ret_72h = float(last_close / float(close_72.iloc[0]) - 1.0) if len(close_72) > 1 and float(close_72.iloc[0]) > 0 else 0.0
        ma_gap_72h = float(last_close / float(close_72.mean()) - 1.0) if float(close_72.mean()) > 0 else 0.0
        raw_momentum = (price_ret_24h * 3.0) + (price_ret_72h * 1.5) + (ma_gap_72h * 2.0)
        directional_momentum = clamp(raw_momentum / 0.18, -1.0, 1.0)
        time_series = compute_time_series_confirmation(close_72, realized_vol_5m)

        funding_path = data_dir / f"{stem}-1h-funding_rate.feather"
        funding_frame = pd.read_feather(funding_path) if funding_path.exists() else None

        metrics.append(
            {
                "pair": pair,
                "stem": stem,
                "rows_72h": int(len(recent_72h)),
                "history_days": round(history_days, 2),
                "first_timestamp": str(dates_all.iloc[0]),
                "last_timestamp": str(pd.to_datetime(recent_72h["date"].iloc[-1], utc=True)),
                "quote_volume_24h": round(quote_volume_24h, 2),
                "quote_volume_72h_avg": round(quote_volume_72h_avg, 2),
                "persistence_score": round(compute_persistence_score(quote_volume_24h, quote_volume_72h_avg), 4),
                "stability_score": round(compute_stability_score(recent_72h, quote_72), 4),
                "funding_score": round(compute_funding_score(funding_frame), 4),
                "volatility_score": round(compute_volatility_score(realized_vol_5m), 4),
                "realized_vol_5m": round(realized_vol_5m, 6),
                "price_ret_24h": round(price_ret_24h, 5),
                "price_ret_72h": round(price_ret_72h, 5),
                "ma_gap_72h": round(ma_gap_72h, 5),
                "directional_momentum_score": round(directional_momentum, 4),
                "momentum_score": round(abs(directional_momentum), 4),
                **time_series,
            }
        )
    return metrics


def build_output(metrics: List[Dict], top_n: int, benchmark_regime: Dict | None = None, market_cap_stats: Dict | None = None) -> Dict:
    if not metrics:
        raise RuntimeError("No eligible pairs were found for the dynamic universe.")

    frame = pd.DataFrame(metrics)
    freshest = pd.to_datetime(frame["last_timestamp"], utc=True).max()
    recency_hours = (freshest - pd.to_datetime(frame["last_timestamp"], utc=True)).dt.total_seconds() / 3600.0
    frame["recency_score"] = recency_hours.apply(lambda hours: clamp(1.0 - (hours / 6.0)))
    frame["quote24_rank"] = frame["quote_volume_24h"].rank(method="average", pct=True)
    frame["quote72_rank"] = frame["quote_volume_72h_avg"].rank(method="average", pct=True)
    if "market_cap_score" not in frame.columns:
        frame["market_cap_score"] = 0.0
    if "momentum_score" not in frame.columns:
        frame["momentum_score"] = 0.0
    if "trend_confirmation_score" not in frame.columns:
        frame["trend_confirmation_score"] = 0.0
    if "trend_direction_score" not in frame.columns:
        frame["trend_direction_score"] = 0.0
    btc_signal = (benchmark_regime or {}).get("btc") or {}
    eth_signal = (benchmark_regime or {}).get("eth") or {}
    benchmark_ret_24h = float(np.mean([float(item.get("ret_24h", 0.0) or 0.0) for item in (btc_signal, eth_signal) if item.get("available")])) if any(item.get("available") for item in (btc_signal, eth_signal)) else 0.0
    benchmark_ret_72h = float(np.mean([float(item.get("ret_72h", 0.0) or 0.0) for item in (btc_signal, eth_signal) if item.get("available")])) if any(item.get("available") for item in (btc_signal, eth_signal)) else 0.0
    frame["relative_strength_24h"] = frame["price_ret_24h"] - benchmark_ret_24h
    frame["relative_strength_72h"] = frame["price_ret_72h"] - benchmark_ret_72h
    frame["relative_strength_raw"] = (frame["relative_strength_24h"] * 3.0) + (frame["relative_strength_72h"] * 1.5) + (frame["ma_gap_72h"] * 1.0)
    frame["relative_strength_score"] = frame["relative_strength_raw"].apply(lambda value: clamp(float(value) / 0.18, -1.0, 1.0))
    frame["cross_sectional_rank"] = frame["relative_strength_score"].rank(method="average", pct=True)
    regime_name = str((benchmark_regime or {}).get("regime") or "unknown")
    if regime_name == "risk_on":
        frame["regime_alignment_score"] = frame["relative_strength_score"].apply(lambda value: clamp((float(value) + 1.0) / 2.0))
    elif regime_name == "risk_off":
        # In risk-off markets, prefer names with cleaner relative behavior, but do not require long-only strength.
        frame["regime_alignment_score"] = frame["relative_strength_score"].apply(lambda value: clamp((abs(float(value)) + 0.25) / 1.25))
    else:
        frame["regime_alignment_score"] = frame["relative_strength_score"].apply(lambda value: clamp((abs(float(value)) + 0.15) / 1.15))

    has_market_cap = float(frame["market_cap_score"].max() or 0.0) > 0.0
    if has_market_cap:
        frame["overall_score"] = (
            frame["quote24_rank"] * 0.26
            + frame["quote72_rank"] * 0.12
            + frame["market_cap_score"] * 0.18
            + frame["momentum_score"] * 0.06
            + frame["cross_sectional_rank"] * 0.10
            + frame["regime_alignment_score"] * 0.05
            + frame["trend_confirmation_score"] * 0.07
            + frame["persistence_score"] * 0.10
            + frame["stability_score"] * 0.10
            + frame["funding_score"] * 0.04
            + frame["volatility_score"] * 0.03
            + frame["recency_score"] * 0.02
        ) * 100.0
    else:
        frame["overall_score"] = (
            frame["quote24_rank"] * 0.31
            + frame["quote72_rank"] * 0.15
            + frame["momentum_score"] * 0.06
            + frame["cross_sectional_rank"] * 0.12
            + frame["regime_alignment_score"] * 0.07
            + frame["trend_confirmation_score"] * 0.08
            + frame["persistence_score"] * 0.10
            + frame["stability_score"] * 0.10
            + frame["funding_score"] * 0.07
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
        "benchmark_regime": benchmark_regime or {},
        "market_cap_filter": market_cap_stats or {},
        "ranking": ranked.to_dict(orient="records"),
    }


def write_markdown(path: Path, payload: Dict) -> None:
    lines = [
        "# OpenClaw Dynamic Alt Universe",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Freshest market timestamp: {payload['freshest_market_timestamp']}",
        f"- Selected count: {len(payload['selected_pairs'])}",
    ]
    regime = payload.get("benchmark_regime") or {}
    if regime:
        lines.append(
            f"- BTC/ETH regime: {regime.get('regime', 'unknown')} | trend_score={regime.get('combined_trend_score', 'N/A')} | risk_scale={regime.get('risk_scale', 'N/A')}"
        )
    market_filter = payload.get("market_cap_filter") or {}
    if market_filter:
        lines.append(
            f"- Market-cap filter: source={market_filter.get('source', 'none')} | matched={market_filter.get('matched', 0)} | records={market_filter.get('records', 0)}"
        )
    lines += [
        "",
        "## Selected Pairs",
        "",
        ", ".join(payload["selected_pairs"]) if payload["selected_pairs"] else "none",
        "",
        "## Ranking",
        "",
        "| Pair | Score | Market Rank | History Days | 24h Ret | 72h Ret | Relative Strength | Regime Align | Trend Confirm | Trend Dir | Momentum | Quote Vol 24h | Quote Vol 72h Avg | Persistence | Stability | Funding Risk | Volatility | Recency |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in payload["ranking"]:
        market_rank = item.get("market_cap_rank") or ""
        lines.append(
            f"| {item['pair']} | {item['overall_score']} | {market_rank} | {item.get('history_days', 0)} | "
            f"{item.get('price_ret_24h', 0)} | {item.get('price_ret_72h', 0)} | {round(float(item.get('relative_strength_score', 0)), 4)} | "
            f"{round(float(item.get('regime_alignment_score', 0)), 4)} | {round(float(item.get('trend_confirmation_score', 0)), 4)} | "
            f"{round(float(item.get('trend_direction_score', 0)), 4)} | {item.get('directional_momentum_score', 0)} | {item['quote_volume_24h']} | "
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
    parser.add_argument("--min-history-days", type=float, default=0.0)
    parser.add_argument("--market-cap-source", choices=["none", "coingecko"], default="none")
    parser.add_argument("--market-cap-cache", default="")
    parser.add_argument("--market-cap-top-n", type=int, default=250)
    parser.add_argument("--market-cap-pages", type=int, default=1)
    parser.add_argument("--market-cap-cache-max-age-hours", type=float, default=12.0)
    parser.add_argument("--min-market-cap-usd", type=float, default=0.0)
    parser.add_argument("--min-market-volume-usd", type=float, default=0.0)
    parser.add_argument("--max-volume-to-market-cap-ratio", type=float, default=0.0)
    parser.add_argument("--require-market-cap", action="store_true")
    parser.add_argument("--deny-symbols", default=",".join(sorted(DEFAULT_DENY_SYMBOLS)))
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    base_config_path = Path(args.base_config)
    output_config_path = Path(args.output_config)
    output_json_path = Path(args.output_json)
    output_md_path = Path(args.output_md)
    exclude_pairs = {item.strip() for item in args.exclude_pairs.split(",") if item.strip()}

    raw_metrics = load_market_metrics(data_dir, exclude_pairs, args.min_rows_72h, args.min_history_days)
    metrics = raw_metrics
    market_cap_stats = {"source": "none"}
    deny_symbols = {item.strip().upper() for item in args.deny_symbols.split(",") if item.strip()}
    if args.market_cap_source == "coingecko":
        cache_path = Path(args.market_cap_cache) if args.market_cap_cache else output_json_path.parent / "coingecko-market-cap-cache.json"
        try:
            records, source = fetch_coingecko_markets(
                cache_path=cache_path,
                pages=args.market_cap_pages,
                per_page=min(max(args.market_cap_top_n, 1), 250),
                timeout_seconds=20,
                cache_max_age_hours=args.market_cap_cache_max_age_hours,
            )
            filtered, market_cap_stats = enrich_with_market_cap_filter(
                raw_metrics,
                records,
                source,
                args.require_market_cap,
                args.market_cap_top_n,
                args.min_market_cap_usd,
                args.min_market_volume_usd,
                args.max_volume_to_market_cap_ratio,
                deny_symbols,
            )
            if filtered:
                metrics = filtered
            else:
                market_cap_stats["fallback"] = "empty_filter_result_used_local_metrics"
        except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            market_cap_stats = {"source": "coingecko", "error": str(exc), "fallback": "local_metrics"}

    benchmark_regime = build_benchmark_regime(data_dir)
    payload = build_output(metrics, args.top_n, benchmark_regime=benchmark_regime, market_cap_stats=market_cap_stats)

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

