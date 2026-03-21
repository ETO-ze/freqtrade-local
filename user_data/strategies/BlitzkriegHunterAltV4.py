import logging
from typing import Any

from freqtrade.strategy import DecimalParameter

from BlitzkriegHunterAltV3 import BlitzkriegHunterAltV3


logger = logging.getLogger(__name__)


class BlitzkriegHunterAltV4(BlitzkriegHunterAltV3):
    """
    V4 keeps the BTC regime guard from V3, restores the original aggressive
    leverage ladder, and adds pair-level auto screening plus Freqtrade protections.
    """

    DEFAULT_MAX_LEVERAGE = 20.0
    max_leverage = DEFAULT_MAX_LEVERAGE

    leverage_high = DecimalParameter(15.0, 20.0, default=20.0, space="buy", optimize=False)
    leverage_mid = DecimalParameter(8.0, 12.0, default=10.0, space="buy", optimize=False)
    leverage_low = DecimalParameter(3.0, 7.0, default=5.0, space="buy", optimize=False)
    leverage_min = DecimalParameter(1.5, 3.0, default=2.0, space="buy", optimize=False)

    auto_filter_lookback = 36
    auto_filter_min_volume_ratio = 0.85
    auto_filter_max_candle_range = 0.075
    auto_filter_min_body_ratio = 0.18
    auto_filter_max_realized_vol = 0.028
    auto_filter_min_directional_move = 0.012

    @property
    def protections(self):
        return [
            {"method": "CooldownPeriod", "stop_duration_candles": 4},
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 48,
                "trade_limit": 2,
                "stop_duration_candles": 12,
                "only_per_pair": False,
            },
            {
                "method": "LowProfitPairs",
                "lookback_period_candles": 96,
                "trade_limit": 4,
                "stop_duration_candles": 24,
                "required_profit": 0.01,
            },
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 96,
                "trade_limit": 8,
                "stop_duration_candles": 24,
                "max_allowed_drawdown": 0.12,
            },
        ]

    def _passes_pair_auto_filter(self, pair: str) -> bool:
        if not self.dp:
            return True

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or dataframe.empty or len(dataframe) < self.auto_filter_lookback:
            return False

        recent = dataframe.tail(self.auto_filter_lookback)
        last_candle = recent.iloc[-1]

        open_price = float(last_candle.get("open", 0.0) or 0.0)
        high_price = float(last_candle.get("high", 0.0) or 0.0)
        low_price = float(last_candle.get("low", 0.0) or 0.0)
        close_price = float(last_candle.get("close", 0.0) or 0.0)
        volume_ratio = float(last_candle.get("volume_ratio", 1.0) or 1.0)

        if open_price <= 0 or close_price <= 0:
            return False

        candle_range = (high_price - low_price) / open_price if open_price else 0.0
        body_ratio = abs(close_price - open_price) / max(high_price - low_price, 1e-9)
        realized_vol = float(recent["close"].pct_change().dropna().std() or 0.0)
        directional_move = abs(float(recent["close"].iloc[-1] / recent["close"].iloc[0] - 1.0))

        passes = (
            volume_ratio >= self.auto_filter_min_volume_ratio
            and candle_range <= self.auto_filter_max_candle_range
            and body_ratio >= self.auto_filter_min_body_ratio
            and realized_vol <= self.auto_filter_max_realized_vol
            and directional_move >= self.auto_filter_min_directional_move
        )

        if not passes:
            logger.info(
                "Auto-filter blocked %s: volume_ratio=%.2f range=%.3f body=%.3f vol=%.3f move=%.3f",
                pair,
                volume_ratio,
                candle_range,
                body_ratio,
                realized_vol,
                directional_move,
            )

        return passes

    def confirm_trade_entry(
        self,
        pair: str,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        current_time,
        entry_tag: str | None,
        side: str,
        **kwargs: Any,
    ) -> bool:
        if not self._passes_pair_auto_filter(pair):
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
