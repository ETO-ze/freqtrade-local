from BlitzkriegHunterAltV53 import BlitzkriegHunterAltV53


class BlitzkriegHunterAltV541(BlitzkriegHunterAltV53):
    """
    V5.4.1 keeps the V5.3 trade logic and only uses the ML daily screen as
    an outer pause filter. The strategy still decides entries itself, but
    pairs classified as "pause" are blocked from opening new trades.
    """

    paused_pairs = {
        "MEME/USDT:USDT",
        "W/USDT:USDT",
        "F/USDT:USDT",
        "ONE/USDT:USDT",
        "DOOD/USDT:USDT",
        "HMSTR/USDT:USDT",
        "PEPE/USDT:USDT",
        "MEW/USDT:USDT",
        "SPACE/USDT:USDT",
        "TRIA/USDT:USDT",
        "NEIRO/USDT:USDT",
        "ROBO/USDT:USDT",
        "ZIL/USDT:USDT",
        "LINEA/USDT:USDT",
        "BONK/USDT:USDT",
        "PEOPLE/USDT:USDT",
        "HUMA/USDT:USDT",
        "SAHARA/USDT:USDT",
    }

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
        if pair in self.paused_pairs:
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
