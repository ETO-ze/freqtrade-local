from __future__ import annotations

from functools import reduce

import pandas as pd
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from pandas import DataFrame


class MainstreamHunterV2(IStrategy):
    """
    Pure BTC/ETH medium-term futures strategy.

    Design goals:
    - Stable, slower trading style on 4h / 1d.
    - Trade only BTC and ETH.
    - Use 1d trend as regime filter.
    - Use ETH/BTC relative-strength as a mild rotation filter (not a hard blocker).
    - Use funding-rate as a crowding filter for entries and as an early risk signal for exits.
    """

    INTERFACE_VERSION = 3

    timeframe = "4h"
    can_short = True
    startup_candle_count = 360

    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    minimal_roi = {
        "0": 0.10,
        "360": 0.05,
        "1080": 0.02,
    }

    stoploss = -0.09
    trailing_stop = True
    trailing_stop_positive = 0.018
    trailing_stop_positive_offset = 0.035
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
        dataframe["donchian_high"] = dataframe["high"].rolling(20).max()
        dataframe["donchian_low"] = dataframe["low"].rolling(20).min()
        dataframe["donchian_mid"] = (dataframe["donchian_high"] + dataframe["donchian_low"]) / 2.0

        if "eth_usdt_usdt_close_1d" in dataframe.columns and "btc_usdt_usdt_close_1d" in dataframe.columns:
            dataframe["eth_btc_ratio"] = dataframe["eth_usdt_usdt_close_1d"] / dataframe["btc_usdt_usdt_close_1d"]
            dataframe["eth_btc_ratio_ema"] = dataframe["eth_btc_ratio"].ewm(span=20, adjust=False).mean()
        else:
            dataframe["eth_btc_ratio"] = 1.0
            dataframe["eth_btc_ratio_ema"] = 1.0

        dataframe = self._merge_funding_rate(dataframe, metadata["pair"])

        dataframe["bull_regime"] = (
            (dataframe["close_1d"] > dataframe["ema_50_1d"])
            & (dataframe["ema_20_1d"] > dataframe["ema_50_1d"])
            & (dataframe["adx_1d"] > 18)
        ).astype("int")

        dataframe["bear_regime"] = (
            (dataframe["close_1d"] < dataframe["ema_50_1d"])
            & (dataframe["ema_20_1d"] < dataframe["ema_50_1d"])
            & (dataframe["adx_1d"] > 18)
        ).astype("int")

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]
        is_eth = pair.startswith("ETH/")
        is_btc = pair.startswith("BTC/")

        trend_long = (
            (dataframe["ema_20"] > dataframe["ema_50"])
            & (dataframe["ema_50"] > dataframe["ema_100"])
            & (dataframe["rsi"].between(52, 72))
        )
        trend_short = (
            (dataframe["ema_20"] < dataframe["ema_50"])
            & (dataframe["ema_50"] < dataframe["ema_100"])
            & (dataframe["rsi"].between(28, 48))
        )

        breakout_long = (
            (dataframe["close"] > dataframe["donchian_high"].shift(1))
            | (
                (dataframe["close"] > dataframe["ema_20"])
                & (dataframe["close"].shift(1) <= dataframe["ema_20"].shift(1))
                & (dataframe["close"] > dataframe["donchian_mid"])
            )
        )
        breakout_short = (
            (dataframe["close"] < dataframe["donchian_low"].shift(1))
            | (
                (dataframe["close"] < dataframe["ema_20"])
                & (dataframe["close"].shift(1) >= dataframe["ema_20"].shift(1))
                & (dataframe["close"] < dataframe["donchian_mid"])
            )
        )

        long_conditions = [
            dataframe["bull_regime"] == 1,
            trend_long,
            breakout_long,
            dataframe["atr_pct"].between(0.008, 0.075),
            dataframe["funding_rate_24h"] < 0.0008,
            dataframe["funding_rate_72h"] < 0.0012,
        ]

        short_conditions = [
            dataframe["bear_regime"] == 1,
            trend_short,
            breakout_short,
            dataframe["atr_pct"].between(0.008, 0.075),
            dataframe["funding_rate_24h"] > -0.0008,
            dataframe["funding_rate_72h"] > -0.0012,
        ]

        if is_eth:
            long_conditions.append(dataframe["eth_btc_ratio"] > dataframe["eth_btc_ratio_ema"] * 0.995)
            short_conditions.append(dataframe["eth_btc_ratio"] < dataframe["eth_btc_ratio_ema"] * 1.005)

        if is_btc:
            long_conditions.append(dataframe["eth_btc_ratio"] < dataframe["eth_btc_ratio_ema"] * 1.03)
            short_conditions.append(dataframe["eth_btc_ratio"] > dataframe["eth_btc_ratio_ema"] * 0.97)

        dataframe.loc[
            reduce(lambda x, y: x & y, long_conditions),
            ["enter_long", "enter_tag"],
        ] = (1, "midterm_trend_long")

        dataframe.loc[
            reduce(lambda x, y: x & y, short_conditions),
            ["enter_short", "enter_tag"],
        ] = (1, "midterm_trend_short")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe["close"] < dataframe["ema_20"])
                | (dataframe["funding_rate_24h"] > 0.0012)
                | (dataframe["bull_regime"] == 0)
            ),
            ["exit_long", "exit_tag"],
        ] = (1, "midterm_long_exit")

        dataframe.loc[
            (
                (dataframe["close"] > dataframe["ema_20"])
                | (dataframe["funding_rate_24h"] < -0.0012)
                | (dataframe["bear_regime"] == 0)
            ),
            ["exit_short", "exit_tag"],
        ] = (1, "midterm_short_exit")

        return dataframe

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
        if pair.startswith("BTC/"):
            return min(2.5, max_leverage)
        if pair.startswith("ETH/"):
            return min(2.0, max_leverage)
        return min(2.0, max_leverage)
