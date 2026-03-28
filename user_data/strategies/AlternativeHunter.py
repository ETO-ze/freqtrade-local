import json
import logging
import os
from pathlib import Path
from typing import Any

from BlitzkriegHunterAltV53 import BlitzkriegHunterAltV53


logger = logging.getLogger(__name__)


class AlternativeHunter(BlitzkriegHunterAltV53):
    """
    Adaptive wrapper around V53.

    The strategy core stays stable, while OpenClaw updates a runtime policy file
    that controls pair allow/deny, direction bias, stake scaling, leverage cap,
    and optional tuning weights for backtest experimentation.
    """

    policy_file = Path(__file__).resolve().parents[1] / "model_runtime_policy.json"
    _policy_cache_mtime = None
    _policy_cache: dict[str, Any] = {}

    min_bias_block_strength = 0.015
    recent_weight_max_boost = 0.35
    opposite_side_penalty = 0.45

    # Runtime policy keys.
    KEY_BLOCKED = "blocked"
    KEY_ALLOW_LONG = "allow_long"
    KEY_ALLOW_SHORT = "allow_short"
    KEY_DIRECTION_BIAS = "direction_bias"
    KEY_STAKE_SCALE = "stake_scale"
    KEY_LEVERAGE_CAP = "leverage_cap"
    KEY_RECENT_WEIGHT = "recent_weight"
    KEY_BIAS_STRENGTH = "bias_strength"
    KEY_ENTRY_CONFIDENCE_FLOOR = "entry_confidence_floor"
    KEY_TREND_STRENGTH_MULTIPLIER = "trend_strength_multiplier"
    KEY_BREAKOUT_VOLUME_MULTIPLIER = "breakout_volume_multiplier"
    KEY_TREND_VOLUME_MULTIPLIER = "trend_volume_multiplier"
    KEY_VOLATILITY_CEILING_MULTIPLIER = "volatility_ceiling_multiplier"

    SIGNAL_STRUCTURES_TREND = {"TREND", "BREAKOUT"}
    SIGNAL_STRUCTURES_BREAKOUT = {"BREAKOUT"}

    def _policy_path(self) -> Path:
        custom = os.getenv("FT_RUNTIME_POLICY_PATH")
        if custom:
            try:
                return Path(custom)
            except Exception:
                return self.policy_file
        return self.policy_file

    def _tuning(self) -> dict[str, Any]:
        policy = self._load_runtime_policy()
        tuning = policy.get("tuning") or {}
        return tuning if isinstance(tuning, dict) else {}

    def _tuned_float(self, key: str, default: float) -> float:
        try:
            return float(self._tuning().get(key, default))
        except Exception:
            return default

    def _load_runtime_policy(self) -> dict[str, Any]:
        path = self._policy_path()
        if not path.exists():
            return {}

        stat = path.stat()
        if self._policy_cache_mtime == stat.st_mtime and self._policy_cache:
            return self._policy_cache

        try:
            self._policy_cache = json.loads(path.read_text(encoding="utf-8-sig"))
            self._policy_cache_mtime = stat.st_mtime
            return self._policy_cache
        except Exception as exc:
            logger.warning("Failed to load runtime policy from %s: %s", path, exc)
            return {}

    def _pair_policy(self, pair: str) -> dict[str, Any]:
        pairs = self._load_runtime_policy().get("pairs") or {}
        raw_policy = pairs.get(pair) or {}
        return raw_policy if isinstance(raw_policy, dict) else {}

    def _latest_candle(self, pair: str) -> dict[str, Any]:
        if not getattr(self, "dp", None):
            return {}

        try:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        except Exception:
            return {}

        if dataframe is None or dataframe.empty:
            return {}

        try:
            candle = dataframe.iloc[-1]
        except Exception:
            return {}

        return candle.to_dict() if hasattr(candle, "to_dict") else {}

    def _pair_direction_bias(self, pair_policy: dict[str, Any]) -> str:
        bias = str(pair_policy.get(self.KEY_DIRECTION_BIAS, "both") or "both").lower()
        return bias if bias in {"long", "short", "both"} else "both"

    def _pair_flag(self, pair_policy: dict[str, Any], key: str, default: bool) -> bool:
        value = pair_policy.get(key, default)
        return bool(default if value is None else value)

    def _policy_float(
        self,
        pair_policy: dict[str, Any],
        key: str,
        default: float,
        minimum: float | None = None,
        maximum: float | None = None,
    ) -> float:
        try:
            value = float(pair_policy.get(key, default))
        except Exception:
            value = default

        if minimum is not None:
            value = max(minimum, value)
        if maximum is not None:
            value = min(maximum, value)
        return value

    def _side_allowed(self, pair: str, side: str) -> bool:
        pair_policy = self._pair_policy(pair)
        if not pair_policy:
            return True

        if self._pair_flag(pair_policy, self.KEY_BLOCKED, False):
            return False

        if side == "long" and not self._pair_flag(pair_policy, self.KEY_ALLOW_LONG, True):
            return False

        if side == "short" and not self._pair_flag(pair_policy, self.KEY_ALLOW_SHORT, True):
            return False

        return True

    def _recent_weight(self, pair_policy: dict[str, Any]) -> float:
        try:
            return min(max(float(pair_policy.get(self.KEY_RECENT_WEIGHT, 0.0)), 0.0), 1.0)
        except Exception:
            return 0.0

    def _bias_strength(self, pair_policy: dict[str, Any]) -> float:
        try:
            return max(float(pair_policy.get(self.KEY_BIAS_STRENGTH, 0.0)), 0.0)
        except Exception:
            return 0.0

    def _base_scale(self, pair_policy: dict[str, Any]) -> float:
        try:
            return float(pair_policy.get(self.KEY_STAKE_SCALE, 1.0) or 1.0)
        except Exception:
            return 1.0

    def _tuning_bundle(self) -> dict[str, float]:
        return {
            "same_side_recent_boost": self._tuned_float("same_side_recent_boost", 0.5),
            "same_side_bias_multiplier": self._tuned_float("same_side_bias_multiplier", 4.0),
            "opposite_side_penalty": self._tuned_float("opposite_side_penalty", self.opposite_side_penalty),
            "opposite_side_recent_penalty": self._tuned_float("opposite_side_recent_penalty", 0.2),
            "minimum_side_multiplier": self._tuned_float("minimum_side_multiplier", 0.1),
            "max_volatility_multiplier": self._tuned_float("max_volatility_multiplier", 1.8),
            "breakout_volume_multiplier": self._tuned_float("breakout_volume_multiplier", 0.5),
            "trend_volume_multiplier": self._tuned_float("trend_volume_multiplier", 0.35),
        }

    def _entry_thresholds(self, pair_policy: dict[str, Any]) -> dict[str, float]:
        tuning = self._tuning_bundle()
        return {
            "entry_confidence_floor": self._policy_float(pair_policy, self.KEY_ENTRY_CONFIDENCE_FLOOR, 0.62, 0.45, 0.95),
            "trend_strength_multiplier": self._policy_float(pair_policy, self.KEY_TREND_STRENGTH_MULTIPLIER, 1.0, 0.7, 1.5),
            "breakout_volume_multiplier": self._policy_float(pair_policy, self.KEY_BREAKOUT_VOLUME_MULTIPLIER, tuning["breakout_volume_multiplier"], 0.15, 1.5),
            "trend_volume_multiplier": self._policy_float(pair_policy, self.KEY_TREND_VOLUME_MULTIPLIER, tuning["trend_volume_multiplier"], 0.10, 1.2),
            "volatility_ceiling_multiplier": self._policy_float(pair_policy, self.KEY_VOLATILITY_CEILING_MULTIPLIER, tuning["max_volatility_multiplier"], 0.60, 3.0),
        }

    def _side_multiplier_from_policy(self, pair_policy: dict[str, Any], side: str) -> float:
        if not pair_policy:
            return 1.0

        direction_bias = self._pair_direction_bias(pair_policy)
        recent_weight = self._recent_weight(pair_policy)
        bias_strength = self._bias_strength(pair_policy)
        base_scale = self._base_scale(pair_policy)
        tuning = self._tuning_bundle()

        multiplier = 1.0

        if direction_bias == side:
            multiplier += min(self.recent_weight_max_boost, recent_weight * tuning["same_side_recent_boost"])
            multiplier += min(0.25, bias_strength * tuning["same_side_bias_multiplier"])
        elif direction_bias != "both":
            multiplier -= tuning["opposite_side_penalty"]
            multiplier -= min(0.20, recent_weight * tuning["opposite_side_recent_penalty"])

        if base_scale < 1.0:
            multiplier *= max(0.25, base_scale)

        return max(tuning["minimum_side_multiplier"], multiplier)

    def _side_multiplier(self, pair: str, side: str) -> float:
        return self._side_multiplier_from_policy(self._pair_policy(pair), side)

    def _direction_bias_blocks_entry(
        self,
        pair_policy: dict[str, Any],
        side: str,
    ) -> bool:
        if not pair_policy:
            return False

        direction_bias = self._pair_direction_bias(pair_policy)
        if direction_bias == "both" or direction_bias == side:
            return False

        bias_strength = self._bias_strength(pair_policy)
        recent_weight = self._recent_weight(pair_policy)
        bias_threshold = self._tuned_float("bias_block_threshold", self.min_bias_block_strength)
        recent_threshold = self._tuned_float("recent_weight_block_threshold", 0.45)
        return bias_strength >= bias_threshold or recent_weight >= recent_threshold

    def _clamp_scaled_value(
        self,
        base_value: float,
        scale_multiplier: float,
        min_value,
        max_value: float,
    ) -> float:
        scaled = float(base_value) * float(scale_multiplier)
        min_allowed = float(min_value) if min_value else 0.0
        return max(min_allowed, min(float(max_value), scaled))

    def _trend_ok(self, candle: dict[str, Any], side: str, thresholds: dict[str, float] | None = None) -> bool:
        if not candle:
            return True

        structure = str(candle.get("structure", "") or "").upper()
        thresholds = thresholds or {}
        trend_multiplier = float(thresholds.get("trend_strength_multiplier", 1.0))
        required_trend_strength = float(self.trend_strength_threshold.value) * trend_multiplier

        trend_strength = candle.get("trend_strength")
        adx_ma = candle.get("adx_ma")
        active_adx = candle.get("active_adx")
        try:
            if trend_strength is not None and adx_ma is not None and active_adx is not None:
                trend_ok = float(trend_strength) >= required_trend_strength and float(adx_ma) >= float(active_adx)
                if structure in self.SIGNAL_STRUCTURES_TREND:
                    return trend_ok or float(adx_ma) >= float(active_adx)
                return trend_ok
        except Exception:
            return True

        return structure in self.SIGNAL_STRUCTURES_TREND

    def _breakout_ok(self, candle: dict[str, Any], side: str) -> bool:
        if not candle:
            return True

        structure = str(candle.get("structure", "") or "").upper()
        if structure in self.SIGNAL_STRUCTURES_BREAKOUT:
            return True

        try:
            close = float(candle.get("close", 0.0) or 0.0)
            ema_fast = float(candle.get("ema_fast", 0.0) or 0.0)
            ema_slow = float(candle.get("ema_slow", 0.0) or 0.0)
        except Exception:
            return True

        if close <= 0 or ema_fast <= 0 or ema_slow <= 0:
            return True

        if side == "long":
            return close >= ema_fast >= ema_slow
        return close <= ema_fast <= ema_slow

    def _volume_ok(self, candle: dict[str, Any], thresholds: dict[str, float] | None = None) -> bool:
        if not candle:
            return True

        thresholds = thresholds or {}
        volume_ratio = candle.get("volume_ratio")
        active_volume = candle.get("active_volume")
        try:
            if volume_ratio is not None and active_volume is not None:
                structure = str(candle.get("structure", "") or "").upper()
                required_ratio = float(thresholds.get("trend_volume_multiplier", self._tuning_bundle()["trend_volume_multiplier"]))
                if structure in self.SIGNAL_STRUCTURES_BREAKOUT:
                    required_ratio = float(thresholds.get("breakout_volume_multiplier", self._tuning_bundle()["breakout_volume_multiplier"]))
                threshold = min(1.0, float(active_volume) * required_ratio)
                return float(volume_ratio) >= threshold
        except Exception:
            return True
        return True

    def _volatility_ok(self, candle: dict[str, Any], thresholds: dict[str, float] | None = None) -> bool:
        if not candle:
            return True

        thresholds = thresholds or {}
        try:
            volatility_ma = candle.get("volatility_ma")
            if volatility_ma is None:
                atr = candle.get("atr")
                close = candle.get("close")
                if atr is not None and close:
                    volatility_ma = float(atr) / float(close)
            if volatility_ma is None:
                return True

            volatility_ma = float(volatility_ma)
            max_multiplier = float(thresholds.get("volatility_ceiling_multiplier", self._tuning_bundle()["max_volatility_multiplier"]))
            return volatility_ma <= max(float(self.volatility_high_threshold.value) * max_multiplier, 0.01)
        except Exception:
            return True

    def _signal_confidence(self, signal_context: dict[str, Any]) -> float:
        if not signal_context:
            return 1.0

        trend_strength = signal_context.get("trend_strength")
        trend_floor = signal_context.get("trend_strength_floor")
        if trend_strength is not None and trend_floor:
            try:
                trend_component = max(0.0, min(1.0, float(trend_strength) / float(trend_floor)))
            except Exception:
                trend_component = 1.0 if signal_context.get("trend_ok", True) else 0.0
        else:
            trend_component = 1.0 if signal_context.get("trend_ok", True) else 0.0

        breakout_component = 1.0 if signal_context.get("breakout_ok", True) else 0.0

        volume_ratio = signal_context.get("volume_ratio")
        volume_floor = signal_context.get("required_volume_ratio")
        if volume_ratio is not None and volume_floor:
            try:
                if float(volume_floor) <= 0:
                    volume_component = 1.0
                else:
                    volume_component = max(0.0, min(1.0, float(volume_ratio) / float(volume_floor)))
            except Exception:
                volume_component = 1.0 if signal_context.get("volume_ok", True) else 0.0
        else:
            volume_component = 1.0 if signal_context.get("volume_ok", True) else 0.0

        volatility_ma = signal_context.get("volatility_ma")
        volatility_ceiling = signal_context.get("max_volatility_allowed")
        if volatility_ma is not None and volatility_ceiling:
            try:
                if float(volatility_ma) <= 0:
                    volatility_component = 1.0
                else:
                    volatility_component = max(0.0, min(1.0, float(volatility_ceiling) / float(volatility_ma)))
            except Exception:
                volatility_component = 1.0 if signal_context.get("volatility_ok", True) else 0.0
        else:
            volatility_component = 1.0 if signal_context.get("volatility_ok", True) else 0.0

        return round(
            (trend_component * 0.35) +
            (breakout_component * 0.25) +
            (volume_component * 0.20) +
            (volatility_component * 0.20),
            4,
        )

    def _signal_context(self, pair: str, side: str) -> dict[str, Any]:
        candle = self._latest_candle(pair)
        pair_policy = self._pair_policy(pair)
        thresholds = self._entry_thresholds(pair_policy)
        required_volume_ratio = None
        max_volatility_allowed = None
        trend_strength_floor = float(self.trend_strength_threshold.value) * thresholds["trend_strength_multiplier"]

        if candle:
            try:
                active_volume = candle.get("active_volume")
                if active_volume is not None:
                    structure = str(candle.get("structure", "") or "").upper()
                    volume_multiplier = thresholds["trend_volume_multiplier"]
                    if structure in self.SIGNAL_STRUCTURES_BREAKOUT:
                        volume_multiplier = thresholds["breakout_volume_multiplier"]
                    required_volume_ratio = min(1.0, float(active_volume) * volume_multiplier)
            except Exception:
                required_volume_ratio = None

            try:
                max_volatility_allowed = max(float(self.volatility_high_threshold.value) * thresholds["volatility_ceiling_multiplier"], 0.01)
            except Exception:
                max_volatility_allowed = None

        trend_ok = self._trend_ok(candle, side, thresholds)
        breakout_ok = self._breakout_ok(candle, side)
        volume_ok = self._volume_ok(candle, thresholds)
        volatility_ok = self._volatility_ok(candle, thresholds)
        return {
            "trend_ok": trend_ok,
            "breakout_ok": breakout_ok,
            "volume_ok": volume_ok,
            "volatility_ok": volatility_ok,
            "structure": candle.get("structure") if candle else None,
            "trend_strength": candle.get("trend_strength") if candle else None,
            "volume_ratio": candle.get("volume_ratio") if candle else None,
            "volatility_ma": candle.get("volatility_ma") if candle else None,
            "trend_strength_floor": trend_strength_floor,
            "required_volume_ratio": required_volume_ratio,
            "max_volatility_allowed": max_volatility_allowed,
            "entry_confidence_floor": thresholds["entry_confidence_floor"],
            "signal_confidence": 0.0,
        }

    def _signal_filter_blocks_entry(self, signal_context: dict[str, Any]) -> tuple[bool, str]:
        if not signal_context:
            return False, ""

        structure = str(signal_context.get("structure", "") or "").upper()
        if not signal_context.get("volatility_ok", True):
            try:
                volatility_ma = float(signal_context.get("volatility_ma") or 0.0)
                max_volatility = float(signal_context.get("max_volatility_allowed") or 0.0)
                if max_volatility > 0 and volatility_ma > (max_volatility * 1.35):
                    return True, "volatility_guard"
            except Exception:
                return True, "volatility_guard"

        if structure in self.SIGNAL_STRUCTURES_BREAKOUT and not signal_context.get("volume_ok", True):
            try:
                volume_ratio = float(signal_context.get("volume_ratio") or 0.0)
                required_volume = float(signal_context.get("required_volume_ratio") or 0.0)
                if required_volume > 0 and volume_ratio < (required_volume * 0.6):
                    return True, "breakout_volume_guard"
            except Exception:
                return True, "breakout_volume_guard"

        confidence = self._signal_confidence(signal_context)
        signal_context["signal_confidence"] = confidence
        confidence_floor = float(signal_context.get("entry_confidence_floor", 0.62) or 0.62)
        if confidence < confidence_floor:
            return True, "entry_confidence_floor"

        return False, ""

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
        pair_policy = self._pair_policy(pair)
        if not self._side_allowed(pair, side):
            logger.info("Runtime policy blocked %s entry for %s at %s.", side, pair, current_time)
            return False

        signal_context = self._signal_context(pair, side)

        if self._direction_bias_blocks_entry(pair_policy, side):
            logger.info("Runtime policy directional bias blocked %s entry for %s at %s.", side, pair, current_time)
            return False

        blocked, reason = self._signal_filter_blocks_entry(signal_context)
        if blocked:
            logger.info("Signal quality blocked %s entry for %s at %s (%s).", side, pair, current_time, reason)
            return False

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Signal context for %s %s: structure=%s trend_ok=%s breakout_ok=%s volume_ok=%s volatility_ok=%s trend_strength=%s volume_ratio=%s volatility_ma=%s",
                pair,
                side,
                signal_context["structure"],
                signal_context["trend_ok"],
                signal_context["breakout_ok"],
                signal_context["volume_ok"],
                signal_context["volatility_ok"],
                signal_context["trend_strength"],
                signal_context["volume_ratio"],
                signal_context["volatility_ma"],
            )

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

    def leverage(
        self,
        pair: str,
        current_time,
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        entry_tag,
        side: str,
        **kwargs,
    ) -> float:
        base = super().leverage(
            pair=pair,
            current_time=current_time,
            current_rate=current_rate,
            proposed_leverage=proposed_leverage,
            max_leverage=max_leverage,
            entry_tag=entry_tag,
            side=side,
            **kwargs,
        )

        pair_policy = self._pair_policy(pair)
        leverage_cap = pair_policy.get(self.KEY_LEVERAGE_CAP)
        leverage_weight = self._tuned_float("leverage_weight", 1.0)
        multiplier = 1.0 + ((self._side_multiplier_from_policy(pair_policy, side) - 1.0) * leverage_weight)

        adjusted = float(base) * multiplier

        try:
            if leverage_cap is None:
                return min(adjusted, float(max_leverage))
            return min(adjusted, float(leverage_cap), float(max_leverage))
        except Exception:
            return base

    def custom_stake_amount(
        self,
        pair: str,
        current_time,
        current_rate: float,
        proposed_stake: float,
        min_stake,
        max_stake: float,
        leverage: float,
        entry_tag,
        side: str,
        **kwargs,
    ) -> float:
        base = super().custom_stake_amount(
            pair=pair,
            current_time=current_time,
            current_rate=current_rate,
            proposed_stake=proposed_stake,
            min_stake=min_stake,
            max_stake=max_stake,
            leverage=leverage,
            entry_tag=entry_tag,
            side=side,
            **kwargs,
        )

        pair_policy = self._pair_policy(pair)
        stake_scale = pair_policy.get(self.KEY_STAKE_SCALE)
        stake_weight = self._tuned_float("stake_weight", 1.0)
        multiplier = 1.0 + ((self._side_multiplier_from_policy(pair_policy, side) - 1.0) * stake_weight)
        if stake_scale is None:
            try:
                return self._clamp_scaled_value(base, multiplier, min_stake, max_stake)
            except Exception:
                return base

        try:
            return self._clamp_scaled_value(base, float(stake_scale) * multiplier, min_stake, max_stake)
        except Exception:
            return base
