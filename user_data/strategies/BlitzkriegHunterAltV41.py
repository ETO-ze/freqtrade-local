import re
from datetime import datetime
from typing import Optional

from BlitzkriegHunterAltV4 import BlitzkriegHunterAltV4


class BlitzkriegHunterAltV41(BlitzkriegHunterAltV4):
    """
    V4.1 keeps V4's auto-filter and protections, but restores aggression only for
    the strongest long trend setups. Shorts and range trades stay capped.
    """

    auto_filter_min_volume_ratio = 1.0
    auto_filter_max_candle_range = 0.06
    auto_filter_max_realized_vol = 0.022
    auto_filter_min_directional_move = 0.015

    def _extract_signal_metadata(self, entry_tag: Optional[str]) -> tuple[str, int]:
        if not entry_tag:
            return "unknown", 0

        signal_type = "unknown"
        if "BREAKOUT" in entry_tag:
            signal_type = "breakout"
        elif "TREND" in entry_tag:
            signal_type = "trend"
        elif "RANGE" in entry_tag:
            signal_type = "range"

        match = re.search(r"_R(\d+)_", entry_tag)
        reliability = int(match.group(1)) if match else 0
        return signal_type, reliability

    def leverage(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        entry_tag: Optional[str],
        side: str,
        **kwargs,
    ) -> float:
        base_leverage = super().leverage(
            pair=pair,
            current_time=current_time,
            current_rate=current_rate,
            proposed_leverage=proposed_leverage,
            max_leverage=max_leverage,
            entry_tag=entry_tag,
            side=side,
            **kwargs,
        )

        signal_type, reliability = self._extract_signal_metadata(entry_tag)

        if side == "short":
            short_cap = 4.0 if reliability < 75 else 6.0
            return min(base_leverage, short_cap)

        if signal_type == "range":
            return min(base_leverage, 5.0)

        if signal_type == "breakout":
            if reliability >= 90:
                return min(base_leverage, 12.0)
            if reliability >= 80:
                return min(base_leverage, 8.0)
            return min(base_leverage, 5.0)

        if signal_type == "trend":
            if reliability >= 85:
                return min(base_leverage, 15.0)
            if reliability >= 75:
                return min(base_leverage, 10.0)
            if reliability >= 65:
                return min(base_leverage, 6.0)
            return min(base_leverage, 4.0)

        return min(base_leverage, 5.0)
