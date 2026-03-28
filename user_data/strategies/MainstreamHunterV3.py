from __future__ import annotations

from functools import reduce

import pandas as pd
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from pandas import DataFrame


class MainstreamHunterV3(IStrategy):
    """
    BTC/ETH medium-term trend strategy.

    Objectives:
    - Lower trade frequency than V2.
    - Keep exposure light in weak / crowded conditions.
    - Scale stake and leverage up only in cleaner trend regimes.
    - Prioritize drawdown control over absolute turnover.
    """

    INTERFACE_VERSION = 3

    timeframe = "4h"
    can_short = True
    startup_candle_count = 420

    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    minimal_roi = {
        "0": 0.12,
        "720": 0.06,
        "2160": 0.025,
    }

    stoploss = -0.08
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.045
    trailing_only_offset_is_reached = True

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "emergency_exit": "market",
        "force_entry": "market",
        "force_exit": "market",
        "stoploss_on_exchange": False,
    }

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema_100"] = ta.EMA(dataframe, timeperiod=100)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        return dataframe

    @informative("1d", asset="ETH/USDT:USDT")
    def populate_indicators_eth_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["close"] = dataframe["close"]
        return dataframe

    @informative("1d", asset="BTC/USDT:USDT")
    def populate_indicators_btc_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["close"] = dataframe["close"]
        return dataframe

    def _merge_funding_rate(self, dataframe: DataFrame, pair: str) -> DataFrame:
        if not self.dp:
            dataframe["funding_rate"] = 0.0
            dataframe["funding_rate_24h"] = 0.0
            dataframe["funding_rate_72h"] = 0.0
            return dataframe

        funding = self.dp.get_pair_dataframe(pair=pair, timeframe="1h", candle_type="funding_rate")
        if funding is None or funding.empty:
            dataframe["funding_rate"] = 0.0
            dataframe["funding_rate_24h"] = 0.0
            dataframe["funding_rate_72h"] = 0.0
            return dataframe

        funding = funding[["date", "open"]].copy()
        funding["date"] = pd.to_datetime(funding["date"], utc=True)
        funding = funding.rename(columns={"open": "funding_rate"}).sort_values("date")
        funding = funding.set_index("date").resample("4h").ffill().reset_index()
        funding["funding_rate_24h"] = funding["funding_rate"].rolling(6, min_periods=1).mean()
        funding["funding_rate_72h"] = funding["funding_rate"].rolling(18, min_periods=1).mean()

        base = dataframe.copy()
        base["date"] = pd.to_datetime(base["date"], utc=True)
        base = pd.merge_asof(
            base.sort_values("date"),
            funding.sort_values("date"),
            on="date",
            direction="backward",
        )

        for column in ["funding_rate", "funding_rate_24h", "funding_rate_72h"]:
            if column not in base.columns:
                base[column] = 0.0
            else:
                base[column] = base[column].fillna(0.0)

        return base

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema_100"] = ta.EMA(dataframe, timeperiod=100)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]
        dataframe["donchian_high"] = dataframe["high"].rolling(55).max()
        dataframe["donchian_low"] = dataframe["low"].rolling(55).min()

        if "eth_usdt_usdt_close_1d" in dataframe.columns and "btc_usdt_usdt_close_1d" in dataframe.columns:
            dataframe["eth_btc_ratio"] = dataframe["eth_usdt_usdt_close_1d"] / dataframe["btc_usdt_usdt_close_1d"]
            dataframe["eth_btc_ratio_ema"] = dataframe["eth_btc_ratio"].ewm(span=30, adjust=False).mean()
        else:
            dataframe["eth_btc_ratio"] = 1.0
            dataframe["eth_btc_ratio_ema"] = 1.0

        dataframe = self._merge_funding_rate(dataframe, metadata["pair"])

        dataframe["bull_regime"] = (
            (dataframe["close_1d"] > dataframe["ema_50_1d"])
            & (dataframe["ema_50_1d"] > dataframe["ema_100_1d"])
            & (dataframe["ema_20_1d"] > dataframe["ema_50_1d"])
            & (dataframe["adx_1d"] > 20)
        ).astype("int")

        dataframe["bear_regime"] = (
            (dataframe["close_1d"] < dataframe["ema_50_1d"])
            & (dataframe["ema_50_1d"] < dataframe["ema_100_1d"])
            & (dataframe["ema_20_1d"] < dataframe["ema_50_1d"])
            & (dataframe["adx_1d"] > 22)
        ).astype("int")

        return dataframe

    def _entry_strength(self, row, pair: str, side: str) -> float:
        score = 0.55

        if side == "long" and row.get("bull_regime", 0) == 1:
            score += 0.20
        if side == "short" and row.get("bear_regime", 0) == 1:
            score += 0.20

        if float(row.get("adx_1d", 0.0) or 0.0) > 25:
            score += 0.08

        atr_pct = float(row.get("atr_pct", 0.0) or 0.0)
        if 0.01 <= atr_pct <= 0.045:
            score += 0.08
        elif atr_pct > 0.06:
            score -= 0.18

        funding_24h = float(row.get("funding_rate_24h", 0.0) or 0.0)
        if side == "long":
            if funding_24h < 0.00035:
                score += 0.06
            elif funding_24h > 0.0010:
                score -= 0.15
        else:
            if funding_24h > -0.00035:
                score += 0.05
            elif funding_24h < -0.0010:
                score -= 0.15

        ratio = float(row.get("eth_btc_ratio", 1.0) or 1.0)
        ratio_ema = float(row.get("eth_btc_ratio_ema", 1.0) or 1.0)
        if pair.startswith("ETH/"):
            if side == "long" and ratio > ratio_ema * 1.01:
                score += 0.08
            if side == "short" and ratio < ratio_ema * 0.995:
                score += 0.08
        elif pair.startswith("BTC/"):
            if side == "long" and ratio <= ratio_ema * 1.03:
                score += 0.05
            if side == "short" and ratio >= ratio_ema * 0.99:
                score += 0.05

        return max(0.40, min(1.25, score))

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]
        is_eth = pair.startswith("ETH/")
        is_btc = pair.startswith("BTC/")

        trend_long = (
            (dataframe["ema_20"] > dataframe["ema_50"])
            & (dataframe["ema_50"] > dataframe["ema_100"])
            & (dataframe["rsi"].between(54, 66))
        )
        trend_short = (
            (dataframe["ema_20"] < dataframe["ema_50"])
            & (dataframe["ema_50"] < dataframe["ema_100"])
            & (dataframe["rsi"].between(34, 46))
        )

        long_conditions = [
            dataframe["bull_regime"] == 1,
            trend_long,
            dataframe["close"] > dataframe["donchian_high"].shift(1),
            dataframe["atr_pct"].between(0.01, 0.06),
            dataframe["funding_rate_24h"] < 0.0010,
            dataframe["funding_rate_72h"] < 0.0014,
        ]

        short_conditions = [
            dataframe["bear_regime"] == 1,
            trend_short,
            dataframe["close"] < dataframe["donchian_low"].shift(1),
            dataframe["atr_pct"].between(0.01, 0.06),
            dataframe["funding_rate_24h"] > -0.0010,
            dataframe["funding_rate_72h"] > -0.0014,
        ]

        if is_eth:
            long_conditions.append(dataframe["eth_btc_ratio"] > dataframe["eth_btc_ratio_ema"] * 1.01)
            short_conditions.append(dataframe["eth_btc_ratio"] < dataframe["eth_btc_ratio_ema"] * 0.995)

        if is_btc:
            long_conditions.append(dataframe["eth_btc_ratio"] <= dataframe["eth_btc_ratio_ema"] * 1.04)
            short_conditions.append(dataframe["eth_btc_ratio"] >= dataframe["eth_btc_ratio_ema"] * 0.99)

        dataframe.loc[
            reduce(lambda x, y: x & y, long_conditions),
            ["enter_long", "enter_tag"],
        ] = (1, "slow_trend_long")

        dataframe.loc[
            reduce(lambda x, y: x & y, short_conditions),
            ["enter_short", "enter_tag"],
        ] = (1, "slow_trend_short")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe["close"] < dataframe["ema_50"])
                | (dataframe["funding_rate_24h"] > 0.0014)
                | (dataframe["bull_regime"] == 0)
            ),
            ["exit_long", "exit_tag"],
        ] = (1, "slow_long_exit")

        dataframe.loc[
            (
                (dataframe["close"] > dataframe["ema_50"])
                | (dataframe["funding_rate_24h"] < -0.0014)
                | (dataframe["bear_regime"] == 0)
            ),
            ["exit_short", "exit_tag"],
        ] = (1, "slow_short_exit")

        return dataframe

    def custom_stake_amount(
        self,
        pair: str,
        current_time,
        current_rate: float,
        proposed_stake: float,
        min_stake,
        max_stake: float,
        leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float:
        base_scale = 1.0 if pair.startswith("BTC/") else 0.85
        strength = 0.75

        if self.dp:
            analyzed, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if analyzed is not None and not analyzed.empty:
                strength = self._entry_strength(analyzed.iloc[-1], pair, side)

        if side == "short":
            strength *= 0.90

        scaled = float(proposed_stake) * base_scale * strength
        min_allowed = float(min_stake) if min_stake else 0.0
        return max(min_allowed, min(float(max_stake), scaled))

    def leverage(
        self,
        pair: str,
        current_time,
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float:
        base = 1.9 if pair.startswith("BTC/") else 1.7
        strength = 0.75

        if self.dp:
            analyzed, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if analyzed is not None and not analyzed.empty:
                strength = self._entry_strength(analyzed.iloc[-1], pair, side)

        if side == "short":
            strength *= 0.90

        adjusted = base * (0.85 + (strength - 0.4) * 0.6)
        cap = 2.2 if pair.startswith("BTC/") else 2.0
        return min(max_leverage, cap, max(1.0, adjusted))
