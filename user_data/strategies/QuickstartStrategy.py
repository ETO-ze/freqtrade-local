from pandas import DataFrame

from freqtrade.strategy import IStrategy


class QuickstartStrategy(IStrategy):
    INTERFACE_VERSION = 3

    can_short = False
    timeframe = "15m"
    startup_candle_count = 30

    minimal_roi = {
        "0": 0.03,
        "60": 0.02,
        "180": 0.01
    }

    stoploss = -0.10

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_fast"] = dataframe["close"].ewm(span=12, adjust=False).mean()
        dataframe["ema_slow"] = dataframe["close"].ewm(span=26, adjust=False).mean()
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe["ema_fast"] > dataframe["ema_slow"]) &
                (dataframe["ema_fast"].shift(1) <= dataframe["ema_slow"].shift(1)) &
                (dataframe["volume"] > 0)
            ),
            "enter_long"
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe["ema_fast"] < dataframe["ema_slow"]) &
                (dataframe["ema_fast"].shift(1) >= dataframe["ema_slow"].shift(1)) &
                (dataframe["volume"] > 0)
            ),
            "exit_long"
        ] = 1
        return dataframe
