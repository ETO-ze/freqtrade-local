import logging

from BlitzkriegHunterAltConservativeV2 import BlitzkriegHunterAltConservativeV2


class BlitzkriegHunterAltV3(BlitzkriegHunterAltConservativeV2):
    btc_guard_pair = "BTC/USDT:USDT"
    btc_guard_timeframe = "1d"
    btc_daily_volatility_limit = 0.05

    def informative_pairs(self):
        return [(self.btc_guard_pair, self.btc_guard_timeframe)]

    def _is_btc_daily_volatility_too_high(self) -> bool:
        if not self.dp:
            return False

        dataframe = self.dp.get_pair_dataframe(self.btc_guard_pair, self.btc_guard_timeframe)
        if dataframe is None or dataframe.empty:
            return False

        candle = dataframe.iloc[-1]
        open_price = candle.get("open", 0)
        high_price = candle.get("high", 0)
        low_price = candle.get("low", 0)
        if not open_price:
            return False

        daily_range = (high_price - low_price) / open_price
        return daily_range > self.btc_daily_volatility_limit

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
        if self._is_btc_daily_volatility_too_high():
            logging.getLogger(__name__).info(
                "BTC daily range exceeds 5%%, blocking new entry for %s at %s.",
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
