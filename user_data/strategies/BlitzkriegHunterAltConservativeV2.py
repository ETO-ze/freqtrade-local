from freqtrade.strategy import DecimalParameter

from BlitzkriegHunterV01 import BlitzkriegHunterV01


class BlitzkriegHunterAltConservativeV2(BlitzkriegHunterV01):
    timeframe = "5m"
    stoploss = -0.10

    DEFAULT_MAX_LEVERAGE = 5.0
    max_leverage = DEFAULT_MAX_LEVERAGE

    leverage_high = DecimalParameter(4.0, 5.0, default=5.0, space="buy", optimize=False)
    leverage_mid = DecimalParameter(2.0, 4.0, default=3.0, space="buy", optimize=False)
    leverage_low = DecimalParameter(1.5, 3.0, default=2.0, space="buy", optimize=False)
    leverage_min = DecimalParameter(1.0, 2.0, default=1.0, space="buy", optimize=False)

    def custom_stoploss(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        stop = super().custom_stoploss(
            pair=pair,
            trade=trade,
            current_time=current_time,
            current_rate=current_rate,
            current_profit=current_profit,
            **kwargs,
        )
        return max(stop, -0.10)
