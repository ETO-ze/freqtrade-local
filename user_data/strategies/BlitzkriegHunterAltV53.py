import logging

from BlitzkriegHunterAltV5 import BlitzkriegHunterAltV5


class BlitzkriegHunterAltV53(BlitzkriegHunterAltV5):
    """
    V5.3 keeps the V5 risk base and adds a pair-level overheat guard so
    breakout-chasing is reduced on highly unstable alt days.
    """

    pair_guard_lookback_candles = 288
    pair_daily_range_limit = 0.12
    pair_daily_close_change_limit = 0.08

    @property
    def protections(self):
        return super().protections + [
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 48,
                "trade_limit": 3,
                "stop_duration_candles": 12,
                "only_per_pair": False,
            }
        ]

    def _is_pair_overheated(self, pair: str) -> bool:
        if not self.dp:
            return False

        dataframe = self.dp.get_pair_dataframe(pair, self.timeframe)
        if dataframe is None or len(dataframe) < self.pair_guard_lookback_candles:
            return False

        recent = dataframe.iloc[-self.pair_guard_lookback_candles :]
        open_price = recent.iloc[0].get("open", 0)
        high_price = recent["high"].max()
        low_price = recent["low"].min()
        close_price = recent.iloc[-1].get("close", 0)
        if not open_price:
            return False

        daily_range = (high_price - low_price) / open_price
        close_change = abs(close_price - open_price) / open_price

        return (
            daily_range > self.pair_daily_range_limit
            or close_change > self.pair_daily_close_change_limit
        )

    def confirm_trade_entry(
        self,
        pair,
        order_type,
        amount,
        rate,
        time_in_force,
        current_time,
        entry_tag,
        side,
        **kwargs,
    ) -> bool:
        if self._is_pair_overheated(pair):
            logging.getLogger(__name__).info(
                "Pair daily move too hot, blocking new entry for %s at %s.",
                pair,
                current_time,
            )
            return False

        return super().confirm_trade_entry(
            pair=pair,
            order_type=order_type,
            amount=amount,
            rate=rate,
            time_in_force=time_in_force,
            current_time=current_time,
            entry_tag=entry_tag,
            side=side,
            **kwargs,
        )
