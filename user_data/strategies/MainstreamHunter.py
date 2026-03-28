from __future__ import annotations

from functools import reduce
from typing import Dict

import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from pandas import DataFrame


class MainstreamHunter(IStrategy):
    """
    Mainstream multi-asset futures skeleton for BTC / ETH / XAU with XAU regime filter.

    Design:
    - Trade BTC/ETH/XAU futures directly.
    - Use XAU perpetual itself as a risk filter for crypto longs.
    - Use ETH/BTC relative strength to rotate bias between BTC and ETH.
    - Keep logic simple and explicit so it can be extended later by OpenClaw outputs.
    """

    INTERFACE_VERSION = 3

    timeframe = "4h"
    can_short = True
    startup_candle_count = 72

    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    minimal_roi = {
        "0": 0.08,
        "240": 0.04,
        "720": 0.015,
    }

    stoploss = -0.08
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.04
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

    @property
    def plot_config(self) -> Dict:
        return {
            "main_plot": {
                "ema_20": {},
                "ema_50": {},
                "ema_200": {},
                "donchian_high": {"color": "green"},
                "donchian_low": {"color": "red"},
            },
            "subplots": {
                "Momentum": {
                    "adx": {},
                    "atr_pct": {},
                },
                "Regime": {
                    "eth_btc_ratio": {},
                    "eth_btc_ratio_ema": {},
                    "xau_regime_strength": {},
                },
            },
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

    @informative("1d", asset="XAU/USDT:USDT")
    def populate_indicators_xau_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]

        dataframe["donchian_high"] = dataframe["high"].rolling(20).max()
        dataframe["donchian_low"] = dataframe["low"].rolling(20).min()

        if "eth_usdt_usdt_close_1d" in dataframe.columns and "btc_usdt_usdt_close_1d" in dataframe.columns:
            dataframe["eth_btc_ratio"] = dataframe["eth_usdt_usdt_close_1d"] / dataframe["btc_usdt_usdt_close_1d"]
            dataframe["eth_btc_ratio_ema"] = dataframe["eth_btc_ratio"].ewm(span=20, adjust=False).mean()
        else:
            dataframe["eth_btc_ratio"] = 1.0
            dataframe["eth_btc_ratio_ema"] = 1.0

        if "xau_usdt_usdt_ema_20_1d" in dataframe.columns and "xau_usdt_usdt_ema_50_1d" in dataframe.columns:
            dataframe["xau_regime_strength"] = (
                dataframe["xau_usdt_usdt_ema_20_1d"] / dataframe["xau_usdt_usdt_ema_50_1d"]
            ) - 1.0
        else:
            dataframe["xau_regime_strength"] = 0.0

        dataframe["bull_regime"] = (
            (dataframe["close_1d"] > dataframe["ema_20_1d"])
            & (dataframe["adx_1d"] > 18)
            & (dataframe["ema_20"] > dataframe["ema_50"])
        ).astype("int")

        dataframe["bear_regime"] = (
            (dataframe["close_1d"] < dataframe["ema_20_1d"])
            & (dataframe["adx_1d"] > 18)
            & (dataframe["ema_20"] < dataframe["ema_50"])
        ).astype("int")

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]
        is_eth = pair.startswith("ETH/")
        is_btc = pair.startswith("BTC/")
        is_xau = pair.startswith("XAU/")

        long_conditions = [
            dataframe["bull_regime"] == 1,
            dataframe["close"] > dataframe["donchian_high"].shift(1),
            dataframe["atr_pct"] < 0.06,
        ]

        short_conditions = [
            dataframe["bear_regime"] == 1,
            dataframe["close"] < dataframe["donchian_low"].shift(1),
            dataframe["atr_pct"] < 0.06,
        ]

        if is_eth:
            long_conditions.append(dataframe["eth_btc_ratio"] > dataframe["eth_btc_ratio_ema"])
            short_conditions.append(dataframe["eth_btc_ratio"] < dataframe["eth_btc_ratio_ema"])
        elif is_btc:
            long_conditions.append(dataframe["eth_btc_ratio"] <= dataframe["eth_btc_ratio_ema"] * 1.01)
            short_conditions.append(dataframe["eth_btc_ratio"] >= dataframe["eth_btc_ratio_ema"] * 0.99)

        # When XAU is structurally strong, suppress crypto longs. Do not block XAU itself.
        if not is_xau:
            long_conditions.append(dataframe["xau_regime_strength"] < 0.03)

        dataframe.loc[
            reduce(lambda x, y: x & y, long_conditions),
            ["enter_long", "enter_tag"],
        ] = (1, "trend_breakout_long")

        dataframe.loc[
            reduce(lambda x, y: x & y, short_conditions),
            ["enter_short", "enter_tag"],
        ] = (1, "trend_breakout_short")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe["close"] < dataframe["ema_20"])
                | (dataframe["close"] < dataframe["ema_50"])
            ),
            ["exit_long", "exit_tag"],
        ] = (1, "ema_trend_fail")

        dataframe.loc[
            (
                (dataframe["close"] > dataframe["ema_20"])
                | (dataframe["close"] > dataframe["ema_50"])
            ),
            ["exit_short", "exit_tag"],
        ] = (1, "ema_trend_fail")

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
            return min(3.0, max_leverage)
        if pair.startswith("ETH/"):
            return min(3.0, max_leverage)
        if pair.startswith("XAU/"):
            return min(2.0, max_leverage)
        return min(2.0, max_leverage)
