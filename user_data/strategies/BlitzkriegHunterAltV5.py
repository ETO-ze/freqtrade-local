from BlitzkriegHunterAltV3 import BlitzkriegHunterAltV3


class BlitzkriegHunterAltV5(BlitzkriegHunterAltV3):
    """
    V5 stays on the V3 risk base and adds light protections for a narrower,
    higher-quality alt basket.
    """

    @property
    def protections(self):
        return [
            {"method": "CooldownPeriod", "stop_duration_candles": 3},
            {
                "method": "LowProfitPairs",
                "lookback_period_candles": 72,
                "trade_limit": 3,
                "stop_duration_candles": 18,
                "required_profit": 0.005,
            },
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 72,
                "trade_limit": 6,
                "stop_duration_candles": 18,
                "max_allowed_drawdown": 0.10,
            },
        ]
