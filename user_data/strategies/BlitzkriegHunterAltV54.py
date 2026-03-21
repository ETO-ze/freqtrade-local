from BlitzkriegHunterAltV53 import BlitzkriegHunterAltV53


class BlitzkriegHunterAltV54(BlitzkriegHunterAltV53):
    """
    V5.4 keeps the V5.3 protections and applies a simple pair-side bias
    inferred from the daily ML screen so obviously weak directions are skipped.
    """

    short_only_pairs = {
        "PIPPIN/USDT:USDT",
        "RVN/USDT:USDT",
    }

    long_only_pairs = {
        "BOME/USDT:USDT",
    }

    pair_daily_range_limit = 0.10
    pair_daily_close_change_limit = 0.07

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
        if side == "long" and pair in self.short_only_pairs:
            return False

        if side == "short" and pair in self.long_only_pairs:
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
