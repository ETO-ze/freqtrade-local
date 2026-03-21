"""
闪电战猎人策略 BlitzkriegHunter V0.15

更新日期:2025年10月22日
作者:fancer
"""

# 标准库导入
import logging
import math
import re
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, Optional, Tuple

# 第三方库导入
import numpy as np
import talib.abstract as ta
from pandas import DataFrame

# Freqtrade导入
from freqtrade.persistence import Trade
from freqtrade.strategy import DecimalParameter, IntParameter, IStrategy


@dataclass(frozen=True)
class MarketStructureConfig:
    """市场结构参数配置(不可变)
    
    为不同市场结构提供专属的技术指标参数配置。
    使用frozen=True确保配置不可变,提升线程安全性。
    
    Attributes:
        cci_length: CCI指标周期
        wma_length: WMA加权移动平均周期
        atr_length: ATR真实波幅周期
        cci_long: CCI多头阈值
        cci_short: CCI空头阈值
        adx: ADX趋势强度阈值
        volume: 成交量倍数阈值
    """
    cci_length: int
    wma_length: int
    atr_length: int
    cci_long: int
    cci_short: int
    adx: int
    volume: float

@dataclass(frozen=True)
class ExtremeMarketInfo:
    """极端行情检测结果(不可变)
    
    用于识别和量化极端市场条件,包括高波动、巨量和急速价格变动。
    极端行情下会调整止损策略以防止误触发。
    
    Attributes:
        is_extreme: 是否为极端行情
        extreme_type: 极端类型(高波动/巨量/急速变动)
        intensity: 极端强度(1.0-5.0)
        volatility_ratio: 波动率比率
        volume_ratio: 成交量比率
        price_change: 价格变化幅度
    """
    is_extreme: bool
    extreme_type: str
    intensity: float
    volatility_ratio: float
    volume_ratio: float
    price_change: float

@dataclass(frozen=True)
class BottomStructureInfo:
    """底部结构识别结果(不可变)
    
    专为空单设计的底部结构识别系统,通过多维度分析识别潜在的市场底部。
    包括成交量分析、价格支撑、K线形态和反转前兆评分。
    
    Attributes:
        is_bottom: 是否为底部结构
        bottom_type: 底部类型(吸筹/双底/锤头/吞没)
        confidence: 置信度(0-100)
        volume_accumulation: 成交量吸筹确认
        price_support: 价格支撑确认
        candle_pattern: K线形态确认
        reversal_score: 反转前兆评分(0-100)
    """
    is_bottom: bool = False
    bottom_type: str = '无'
    confidence: float = 0.0
    volume_accumulation: bool = False
    price_support: bool = False
    candle_pattern: bool = False
    reversal_score: float = 0.0
    
    @classmethod
    def empty(cls) -> 'BottomStructureInfo':
        """创建空底部信息实例
        
        Returns:
            默认值的BottomStructureInfo实例
        """
        return cls()

# StopLossState数据类已移除 - 不再需要复杂的状态管理
# 直接使用trade.max_profit_ratio跟踪最高利润

class BlitzkriegHunterV01(IStrategy):
    """闪电战猎手策略
    
    完整的量化交易策略实现，包含市场分析、信号生成、风险管理等模块。
    """

    INTERFACE_VERSION = 3
    
    # Logger
    logger = logging.getLogger(__name__)
    
    # ========== 常量定义 ==========
    
    # === 默认值常量 ===
    DEFAULT_STOPLOSS = -0.08              # 默认止损(-8%)
    DEFAULT_MIN_LEVERAGE = 2.0            # 最小杠杆倍数
    DEFAULT_MAX_LEVERAGE = 20.0           # 最大杠杆倍数
    DEFAULT_POSITION_RATIO = 0.9          # 最大仓位比例(90%)
    # DEFAULT_INITIAL_POSITION 动态计算: 1/(max_open_trades + 2)
    
    # === 止损范围限制 ===
    STOPLOSS_MIN = -0.20                  # 最大止损(-20%)
    STOPLOSS_MAX = -0.05                  # 最小止损(-5%)
    
    # === 极端行情阈值 ===
    EXTREME_VOLATILITY_MULTIPLIER = 3.0   # 波动率倍数阈值(3倍)
    EXTREME_VOLUME_MULTIPLIER = 5.0       # 成交量倍数阈值(5倍)
    EXTREME_PRICE_CHANGE = 0.05           # 价格变化阈值(5%)
    EXTREME_STOPLOSS_MULTIPLIER = 2.0     # 极端行情止损放宽倍数
    
    # === 波动率分析参数 ===
    VOLATILITY_STDDEV_PERIOD = 20         # 标准差计算周期
    VOLATILITY_BODY_RATIO_MIN = 0.3       # K线实体最小占比(过滤十字星)
    VOLATILITY_HIGH_THRESHOLD_BASE = 0.01 # 高波动基准阈值(1%)
    
    # === 行为确认阈值 ===
    BEHAVIOR_VOLUME_SPIKE = 2.5           # 成交量放大阈值(2.5倍)
    BEHAVIOR_SUPPORT_BREAK_CANDLES = 4    # 支撑位突破确认K线数
    BEHAVIOR_CONSECUTIVE_CANDLES = 3      # 连续反向K线数量
    BEHAVIOR_PRICE_BREAK_LONG = 0.985     # 多单价格突破阈值(-1.5%)
    BEHAVIOR_PRICE_BREAK_SHORT = 1.015    # 空单价格突破阈值(+1.5%)
    
    # === 趋势延续保护参数 ===
    TREND_GUARD_MIN_RELIABILITY = 50      # 启动趋势保护的最低可靠度
    TREND_GUARD_CANDLES = 8               # 趋势保护期(K线数)
    TREND_GUARD_REVERSAL_CONFIRM = 4      # 反转确认K线数
    TREND_GUARD_STRONG_MOVE = 0.01        # 强势移动阈值(1%)
    
    # === 插针检测参数 ===
    WICK_RATIO_THRESHOLD = 0.6            # 影线占比阈值(60%)
    WICK_PROTECTION_MULTIPLIER = 1.2      # 插针保护止损放宽倍数
    
    # === 利润分界点 ===
    PROFIT_THRESHOLD_MIN = 0.012          # 最小利润阈值(1.2%)
    PROFIT_THRESHOLD_SMALL = 0.05         # 小利润阈值(5%)
    PROFIT_THRESHOLD_MEDIUM = 0.20        # 中等利润阈值(20%)
    PROFIT_THRESHOLD_LARGE = 0.50         # 大额利润阈值(50%)
    PROFIT_THRESHOLD_HUGE = 1.00          # 巨额利润阈值(100%)
    
    # === 仓位调整参数 ===
    DCA_REDUCE_THRESHOLD_1 = -0.008       # 第一次减仓阈值(-0.8%)
    DCA_REDUCE_THRESHOLD_2 = -0.012       # 第二次减仓阈值(-1.2%)
    DCA_REDUCE_RATIO_1 = 0.40             # 第一次减仓比例(40%)
    DCA_REDUCE_RATIO_2 = 0.30             # 第二次减仓比例(30%)
    
    # === 内存管理参数 ===
    MAX_PROFIT_DICT_SIZE = 100            # 止损状态字典最大容量
    MAX_PROFIT_DICT_KEEP = 50             # 清理后保留数量
    CACHE_SIZE = 128                      # LRU缓存大小
    
    # === 底部结构识别阈值 ===
    BOTTOM_LOOKBACK_CANDLES = 20          # 底部识别回溯周期
    BOTTOM_VOLUME_ACCUMULATION = 1.5      # 吸筹成交量倍数
    BOTTOM_PRICE_TOLERANCE = 0.005        # 价格支撑容差(0.5%)
    BOTTOM_DOUBLE_BOTTOM_TOLERANCE = 0.01 # 双底容差(1%)
    BOTTOM_HAMMER_WICK_RATIO = 2.0        # 锤头线下影线/实体比率
    BOTTOM_ENGULFING_BODY_RATIO = 1.2     # 吞没形态实体比率
    BOTTOM_CONFIDENCE_THRESHOLD = 60      # 底部置信度阈值
    
    # === 反转前兆评分权重 ===
    REVERSAL_VOLUME_WEIGHT = 0.35         # 成交量权重(35%)
    REVERSAL_VOLATILITY_WEIGHT = 0.25     # 波动率权重(25%)
    REVERSAL_PATTERN_WEIGHT = 0.40        # K线形态权重(40%)
    REVERSAL_SCORE_THRESHOLD = 65         # 反转评分阈值
    
    # ========== 基础配置 ==========

    timeframe = '3m'
    startup_candle_count = 100
    can_short = True
    position_ratio = DEFAULT_POSITION_RATIO
    stoploss = -0.99  # 删除硬止损，完全依赖custom_stoploss动态管理
    minimal_roi = {"0": 100}
    trailing_stop = False
    use_custom_stoploss = True
    process_only_new_candles = False  # 允许K线内多次调用止损
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = True
    
    # ========== 订单配置 ==========

    order_types = {
        'entry': 'limit',
        'exit': 'limit',
        'stoploss': 'market',
        'stoploss_on_exchange': False,
        'stoploss_on_exchange_interval': 60
    }
    order_time_in_force = {
        'entry': 'GTC',
        'exit': 'GTC'
    }
    
    # ========== 智能杠杆配置 ==========

    use_dynamic_leverage = True
    min_leverage = DEFAULT_MIN_LEVERAGE
    max_leverage = DEFAULT_MAX_LEVERAGE
    
    # 杠杆阈值参数 
    leverage_threshold_high = IntParameter(70, 85, default=80, space='buy', optimize=False)     # 高可靠度阈值: 80
    leverage_threshold_mid = IntParameter(55, 70, default=65, space='buy', optimize=False)      # 中可靠度阈值: 65
    leverage_threshold_low = IntParameter(40, 55, default=50, space='buy', optimize=False)      # 低可靠度阈值: 50
    leverage_high = DecimalParameter(15.0, 20.0, default=20.0, space='buy', optimize=False)     # 高可靠度杠杆: 20x
    leverage_mid = DecimalParameter(8.0, 12.0, default=10.0, space='buy', optimize=False)       # 中可靠度杠杆: 10x
    leverage_low = DecimalParameter(3.0, 7.0, default=5.0, space='buy', optimize=False)         # 低可靠度杠杆: 5x
    leverage_min = DecimalParameter(1.5, 3.0, default=2.0, space='buy', optimize=False)         # 最低杠杆: 2x
    
    # ========== Hyperopt优化参数 ==========
    
    # 买入参数 
    trend_strength_threshold = DecimalParameter(0.020, 0.050, default=0.031, space='buy', optimize=False)
    trend_lookback = IntParameter(50, 100, default=76, space='buy', optimize=False)
    volatility_low_threshold = DecimalParameter(0.002, 0.005, default=0.003, space='buy', optimize=False)
    volatility_high_threshold = DecimalParameter(0.003, 0.006, default=0.004, space='buy', optimize=False)
    adx_trending_threshold = DecimalParameter(15.0, 30.0, default=21.2, space='buy', optimize=False)
    adx_ranging_threshold = DecimalParameter(12.0, 25.0, default=17.9, space='buy', optimize=False)
    volume_spike_threshold = DecimalParameter(2.0, 4.0, default=2.8, space='buy', optimize=False)
    
    # 卖出参数
    profit_protection_ratio = DecimalParameter(0.80, 0.95, default=0.828, space='sell', optimize=False)   # 优化后: 0.828
    extreme_protection_ratio = DecimalParameter(0.60, 0.80, default=0.708, space='sell', optimize=False) # 优化后: 0.708
    
    # ========== 🎯 底部识别系统参数 ==========
    
    # 底部结构识别阈值 
    bottom_volume_accumulation = DecimalParameter(1.2, 2.0, default=1.94, space='sell', optimize=False)   # 吸筹成交量倍数: 1.94
    bottom_price_tolerance = DecimalParameter(0.003, 0.008, default=0.003, space='sell', optimize=False)  # 价格支撑容差: 0.003
    bottom_hammer_wick_ratio = DecimalParameter(1.5, 3.0, default=1.993, space='sell', optimize=False)    # 锤头线影线/实体比: 1.993
    bottom_engulfing_body_ratio = DecimalParameter(1.0, 1.5, default=1.2, space='sell', optimize=False)   # 吞没形态实体比: 1.2
    bottom_confidence_threshold = IntParameter(30, 60, default=50, space='sell', optimize=False)          # 底部置信度阈值: 50
    
    # 反转前兆评分权重 
    reversal_volume_weight = DecimalParameter(0.25, 0.45, default=0.35, space='sell', optimize=False)     # 成交量权重: 0.35
    reversal_volatility_weight = DecimalParameter(0.15, 0.35, default=0.25, space='sell', optimize=False) # 波动率权重: 0.25
    reversal_pattern_weight = DecimalParameter(0.30, 0.50, default=0.40, space='sell', optimize=False)    # K线形态权重: 0.40
    reversal_score_threshold = IntParameter(40, 65, default=62, space='sell', optimize=False)             # 反转评分阈值: 62
    reversal_tighten_threshold = DecimalParameter(0.70, 0.90, default=0.80, space='sell', optimize=False) # 收紧止损阈值: 0.80
    reversal_tighten_ratio = DecimalParameter(0.40, 0.70, default=0.50, space='sell', optimize=False)     # 收紧止损比例: 0.50
    
    # ========== 🎯 科学止盈止损参数（ATR标准化 + 风险预算模型）==========
    
    # 核心风险参数（ATR倍数）
    risk_initial_stop_atr = DecimalParameter(1.5, 3.5, default=2.5, space='sell', optimize=False)      # 初始止损：2.5倍ATR
    risk_breakeven_profit_atr = DecimalParameter(1.0, 2.5, default=1.5, space='sell', optimize=False)  # 保本触发：1.5倍ATR利润
    risk_trailing_distance_atr = DecimalParameter(0.5, 2.0, default=1.0, space='sell', optimize=False) # 追踪距离：1.0倍ATR
    
    # 动态调整因子 
    risk_volatility_factor = DecimalParameter(0.5, 1.5, default=1.0, space='sell', optimize=False)    # 波动率调整因子
    risk_trend_factor = DecimalParameter(0.7, 1.3, default=1.0, space='sell', optimize=False)         # 趋势强度调整因子
    risk_time_decay_hours = DecimalParameter(2.0, 12.0, default=6.0, space='sell', optimize=False)    # 时间衰减周期（小时）
    
    # 利润保护曲线参数（sigmoid函数）
    profit_protection_steepness = DecimalParameter(5.0, 20.0, default=10.0, space='sell', optimize=False)  # 保护曲线陡峭度
    profit_protection_midpoint = DecimalParameter(0.05, 0.20, default=0.10, space='sell', optimize=False) # 保护曲线中点（10%利润）
    
    # 自适应止损（根据市场结构 + ATR）
    stoploss_atr_multiplier_trend = DecimalParameter(3.0, 8.0, default=4.523, space='sell', optimize=False)        # TREND: 4.523x ATR
    stoploss_atr_multiplier_range = DecimalParameter(3.0, 7.0, default=3.171, space='sell', optimize=False)        # RANGE: 3.171x ATR
    stoploss_atr_multiplier_breakout = DecimalParameter(4.0, 10.0, default=8.693, space='sell', optimize=False)    # BREAKOUT: 8.693x ATR
    stoploss_atr_multiplier_contraction = DecimalParameter(2.5, 6.0, default=3.787, space='sell', optimize=False)  # CONTRACTION: 3.787x ATR
    
    # 🎯 动态保本阈值 (考虑手续费成本: 开仓0.05% + 平仓0.05% + 滑点0.05% + 安全边际0.35% = 0.5%基础成本)
    breakeven_trend = DecimalParameter(0.015, 0.060, default=0.021, space='sell', optimize=False)      # TREND: 2.1%
    breakeven_range = DecimalParameter(0.015, 0.050, default=0.044, space='sell', optimize=False)      # RANGE: 4.4%
    breakeven_breakout = DecimalParameter(0.015, 0.070, default=0.035, space='sell', optimize=False)   # BREAKOUT: 3.5%
    breakeven_contraction = DecimalParameter(0.015, 0.040, default=0.036, space='sell', optimize=False) # CONTRACTION: 3.6%
    breakeven_extreme = DecimalParameter(0.015, 0.040, default=0.015, space='sell', optimize=False)    # 极端行情: 1.5% (最低保本)
    
    # 防插针参数
    wick_protection_enabled = True
    wick_ratio_threshold = WICK_RATIO_THRESHOLD  # 影线占比>60%认为插针
    
    # 入场质量过滤参数 
    enable_quality_filter = True
    min_reliability_score = IntParameter(20, 60, default=40, space='buy', optimize=False)  # 最低可靠度40分
    
    # ========== 智能止损系统参数 ==========
    
    # 波动率自适应参数
    volatility_stddev_period = VOLATILITY_STDDEV_PERIOD  # 标准差周期
    volatility_body_ratio_min = VOLATILITY_BODY_RATIO_MIN  # K线实体最小占比（过滤十字星）
    volatility_adaptive_multiplier = DecimalParameter(1.5, 3.0, default=2.845, space='sell', optimize=False)  # 关闭优化
    
    # 行为确认参数
    behavior_volume_spike_threshold = BEHAVIOR_VOLUME_SPIKE  # 成交量放大阈值
    behavior_support_break_confirm = BEHAVIOR_SUPPORT_BREAK_CANDLES  # 支撑位突破确认K线数
    behavior_consecutive_candles = BEHAVIOR_CONSECUTIVE_CANDLES  # 连续反向K线数量
    
    # 趋势延续保护参数
    trend_guard_min_reliability = TREND_GUARD_MIN_RELIABILITY  # 启动趋势保护的最低可靠度
    trend_guard_candles = TREND_GUARD_CANDLES  # 趋势保护期
    trend_guard_reversal_confirm = TREND_GUARD_REVERSAL_CONFIRM  # 反转确认K线数
    
    # ========== 🎯 自适应保护系统参数 (已优化,不再优化) ==========
    
    # 新仓位保护参数 (已优化 - 固定值)
    new_position_candles = IntParameter(10, 30, default=15, space='sell', optimize=False)  # 新仓保护期: 15根K线
    new_position_multiplier_low = DecimalParameter(2.0, 3.5, default=2.024, space='sell', optimize=False)   # 亏损<1%倍数: 2.024x
    new_position_multiplier_mid = DecimalParameter(1.5, 2.5, default=1.506, space='sell', optimize=False)   # 亏损1-4.9%倍数: 1.506x
    new_position_multiplier_high = DecimalParameter(1.0, 1.8, default=1.191, space='sell', optimize=False)  # 亏损>4.9%倍数: 1.191x
    new_position_loss_threshold_1 = DecimalParameter(-0.03, -0.01, default=-0.01, space='sell', optimize=False)  # 第一档亏损阈值: -1%
    new_position_loss_threshold_2 = DecimalParameter(-0.08, -0.03, default=-0.049, space='sell', optimize=False)  # 第二档亏损阈值: -4.9%
    
    # 插针保护参数 (已优化 - 固定值)
    wick_protection_multiplier = DecimalParameter(1.2, 2.0, default=1.905, space='sell', optimize=False)  # 插针保护倍数: 1.905x
    
    # 极端行情保护参数 (已优化 - 固定值)
    extreme_protection_multiplier = DecimalParameter(1.2, 2.0, default=1.878, space='sell', optimize=False)  # 极端保护倍数: 1.878x
    
    # 行为确认保护参数 (已优化 - 固定值)
    behavior_protection_multiplier = DecimalParameter(1.2, 1.8, default=1.71, space='sell', optimize=False)  # 行为保护倍数: 1.71x
    behavior_check_threshold = DecimalParameter(0.3, 0.7, default=0.466, space='sell', optimize=False)  # 触发检查阈值: 0.466
    
    # ========== 🎯 止盈止损保护比例参数 ==========
    
    # 小利润区间保护 (1.2%-5%)
    small_profit_protection_ratio = DecimalParameter(0.75, 0.95, default=0.85, space='sell', optimize=True)  # 小利润保护比例: 85%
    small_profit_threshold_min = DecimalParameter(0.010, 0.015, default=0.012, space='sell', optimize=True)  # 小利润区间下限: 1.2%
    
    # 大利润区间保护 (>5%)
    large_profit_base_protection = DecimalParameter(0.70, 0.85, default=0.75, space='sell', optimize=True)   # 大利润基础保护: 75%
    large_profit_max_protection = DecimalParameter(0.92, 0.98, default=0.96, space='sell', optimize=True)    # 大利润最大保护: 96%
    large_profit_curve_steepness = DecimalParameter(0.5, 1.5, default=0.8, space='sell', optimize=True)      # 保护曲线陡峭度: 0.8
    
    # 底部检测置信度阈值 (空单止盈保护)
    bottom_confidence_exit_threshold = IntParameter(30, 60, default=40, space='sell', optimize=True)  # 底部置信度阈值: 40%
    
    # ========== 交易参数 ========== 
    
    # 止盈目标参数 
    profit_target_range = DecimalParameter(0.010, 0.025, default=0.014, space='sell', optimize=False)        # RANGE: 1.4%
    profit_target_contraction = DecimalParameter(0.010, 0.025, default=0.019, space='sell', optimize=False)  # CONTRACTION: 1.9%
    profit_target_trend = DecimalParameter(0.015, 0.030, default=0.015, space='sell', optimize=False)        # TREND: 1.5%
    profit_target_breakout = DecimalParameter(0.018, 0.035, default=0.022, space='sell', optimize=False)     # BREAKOUT: 2.2%
    profit_target_multiplier = DecimalParameter(1.0, 1.5, default=1.475, space='sell', optimize=False)       # 止盈倍数: 1.475
    
    # ========== 保留的兼容性参数（用于其他模块）==========
    profit_threshold_small = PROFIT_THRESHOLD_SMALL    # 5%
    profit_threshold_medium = PROFIT_THRESHOLD_MEDIUM  # 20%
    profit_threshold_large = PROFIT_THRESHOLD_LARGE    # 50%
    profit_threshold_huge = PROFIT_THRESHOLD_HUGE     # 100%
    
    # DCA加仓参数 
    dca_profit_1 = DecimalParameter(0.010, 0.025, default=0.013, space='sell', optimize=False)  # 第1次加仓: 1.3%
    dca_profit_2 = DecimalParameter(0.030, 0.060, default=0.033, space='sell', optimize=False)  # 第2次加仓: 3.3%
    dca_amount_1 = DecimalParameter(0.20, 0.35, default=0.228, space='sell', optimize=False)    # 第1次加仓比例: 22.8%
    dca_amount_2 = DecimalParameter(0.25, 0.40, default=0.37, space='sell', optimize=False)    # 第2次加仓比例: 37%
    
    # ========== 市场结构参数映射 ==========

    STRUCTURE_CONFIGS = {
        'TREND': MarketStructureConfig(22, 9, 18, -30, 30, 15, 1.212),
        'RANGE': MarketStructureConfig(13, 5, 11, -54, 54, 22, 1.393),
        'BREAKOUT': MarketStructureConfig(17, 4, 14, -43, 43, 17, 1.278),
        'CONTRACTION': MarketStructureConfig(13, 5, 11, -54, 54, 22, 1.393)
    }
    
    # ========== 可靠度权重配置 ==========

    reliability_weights = {
        'structure': 0.25,
        'trend_strength': 0.20,
        'momentum': 0.20,
        'volume': 0.15,
        'volatility': 0.10,
        'signal_quality': 0.10
    }
    
    # ========== 极端行情配置 ==========
    extreme_volatility_multiplier = EXTREME_VOLATILITY_MULTIPLIER
    extreme_volume_multiplier = EXTREME_VOLUME_MULTIPLIER
    extreme_price_change = EXTREME_PRICE_CHANGE
    extreme_stoploss_multiplier = EXTREME_STOPLOSS_MULTIPLIER  # 极端行情止损放宽倍数
    
    # ========== 限价单偏移配置 ==========

    ENTRY_OFFSET_RATIOS = {
        'BREAKOUT': 0.05, 'TREND': 0.08, 'CONTRACTION': 0.10, 'RANGE': 0.12
    }
    EXIT_OFFSET_RATIOS = {
        'TREND': 0.10, 'BREAKOUT': 0.08, 'RANGE': 0.05, 'CONTRACTION': 0.05
    }
    
    # ========== 止盈目标配置（动态从参数获取）==========
    
    @property
    def PROFIT_TARGETS(self):
        """动态止盈目标（从Hyperopt参数获取）"""
        return {
            'RANGE': self.profit_target_range.value,
            'CONTRACTION': self.profit_target_contraction.value,
            'TREND': self.profit_target_trend.value,
            'BREAKOUT': self.profit_target_breakout.value
        }
    
    # ========== 状态变量 ==========

    max_balance_reached = 1000.0
    
    # ========== 市场分析模块 ==========

    def _calculate_market_metrics(self, dataframe: DataFrame) -> DataFrame:
        """计算市场度量指标
        
        计算用于市场结构识别的关键指标,包括趋势强度、波动率和成交量。
        
        Args:
            dataframe: 包含OHLCV数据的DataFrame
            
        Returns:
            DataFrame: 添加了以下列的DataFrame
                - trend_strength: 趋势强度(价格变化率)
                - volatility: 波动率(ATR/价格)
                - volatility_ma: 波动率移动平均
                - adx_ma: ADX移动平均
                - volume_ratio: 成交量比率
        """
        lookback = self.trend_lookback.value
        
        dataframe['trend_strength'] = (
            (dataframe['close'] - dataframe['close'].shift(lookback)) / 
            dataframe['close'].shift(lookback)
        ).abs()
        
        dataframe['volatility'] = dataframe['atr'] / dataframe['close']
        dataframe['volatility_ma'] = dataframe['volatility'].rolling(20).mean()
        dataframe['adx_ma'] = dataframe['adx'].rolling(20).mean()
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_ma']
        
        return dataframe
    
    def _detect_breakout(self, dataframe: DataFrame) -> DataFrame:
        """检测价格突破
        
        识别价格突破历史区间的情况,用于市场结构分类。
        
        Args:
            dataframe: 包含OHLCV数据的DataFrame
            
        Returns:
            Series[bool]: 布尔型序列,True表示发生突破
            
        突破定义:
            - 价格突破历史最高价(向上突破)
            - 或价格跌破历史最低价(向下突破)
        """
        lookback = self.trend_lookback.value
        high_max = dataframe['high'].rolling(lookback).max().shift(1)
        low_min = dataframe['low'].rolling(lookback).min().shift(1)
        
        return (dataframe['close'] > high_max) | (dataframe['close'] < low_min)
    
    def identify_market_structure(self, dataframe: DataFrame) -> DataFrame:
        """市场结构识别
        
        基于多维度指标识别当前市场结构,为后续的参数适配和信号生成提供依据。
        
        识别四种市场结构(优先级递减):
            1. **BREAKOUT** - 突破: 价格突破区间 + 高波动 + 成交量激增
            2. **TREND** - 趋势: 强趋势力度 + ADX高位
            3. **CONTRACTION** - 收缩: 低波动 + ADX低位
            4. **RANGE** - 震荡: 默认状态
        
        Args:
            dataframe: 包含OHLCV和技术指标的DataFrame
            
        Returns:
            DataFrame: 添加'structure'列的DataFrame
        """
        dataframe = self._calculate_market_metrics(dataframe)
        is_breakout = self._detect_breakout(dataframe)
        volume_spike = dataframe['volume_ratio'] > self.volume_spike_threshold.value
        
        dataframe['structure'] = 'RANGE'
        
        # 突破：突破 + 高波动 + 成交量激增
        breakout_condition = (
            is_breakout & 
            (dataframe['volatility_ma'] > self.volatility_high_threshold.value) & 
            volume_spike
        )
        dataframe.loc[breakout_condition, 'structure'] = 'BREAKOUT'
        
        # 趋势：强趋势 + 高ADX
        trend_condition = (
            (dataframe['trend_strength'] > self.trend_strength_threshold.value) & 
            (dataframe['adx_ma'] > self.adx_trending_threshold.value) & 
            (dataframe['structure'] != 'BREAKOUT')
        )
        dataframe.loc[trend_condition, 'structure'] = 'TREND'
        
        # 收缩：低波动 + 低ADX
        contraction_condition = (
            (dataframe['volatility_ma'] < self.volatility_low_threshold.value) & 
            (dataframe['adx_ma'] < self.adx_ranging_threshold.value)
        )
        dataframe.loc[contraction_condition, 'structure'] = 'CONTRACTION'
        
        return dataframe
    
    def apply_structure_params(self, dataframe: DataFrame) -> DataFrame:
        """应用结构化参数
        
        根据识别出的市场结构,动态应用不同的技术指标参数。
        这是自适应系统的核心,使策略能够根据市场环境调整行为。
        
        处理流程:
            1. 为每种结构计算专属的CCI和WMA指标
            2. 根据当前结构激活对应的参数组
            3. 生成active_*列供信号生成使用
        
        Args:
            dataframe: 包含'structure'列的DataFrame
            
        Returns:
            DataFrame: 添加active_*列的DataFrame
        """
        # 为每种结构计算专属指标
        for name, config in self.STRUCTURE_CONFIGS.items():
            dataframe[f'cci_{name}'] = ta.CCI(dataframe, timeperiod=config.cci_length)
            dataframe[f'wma_{name}'] = ta.WMA(dataframe, timeperiod=config.wma_length)
        
        # 初始化激活参数列
        for col in ['active_cci', 'active_wma', 'active_cci_long', 
                    'active_cci_short', 'active_adx', 'active_volume']:
            dataframe[col] = 0.0
        
        # 根据当前结构激活对应参数
        for name, config in self.STRUCTURE_CONFIGS.items():
            mask = dataframe['structure'] == name
            if mask.any():
                dataframe.loc[mask, 'active_cci'] = dataframe.loc[mask, f'cci_{name}']
                dataframe.loc[mask, 'active_wma'] = dataframe.loc[mask, f'wma_{name}']
                dataframe.loc[mask, 'active_cci_long'] = config.cci_long
                dataframe.loc[mask, 'active_cci_short'] = config.cci_short
                dataframe.loc[mask, 'active_adx'] = config.adx
                dataframe.loc[mask, 'active_volume'] = config.volume
        
        return dataframe
    
    # ========== 指标计算模块 ==========

    def _calculate_base_indicators(self, dataframe: DataFrame) -> DataFrame:
        """计算基础技术指标
        
        计算策略所需的所有基础技术指标,包括EMA、ADX、DI、成交量和ATR。
        
        Args:
            dataframe: 包含OHLCV数据的DataFrame
            
        Returns:
            DataFrame: 添加了技术指标列的DataFrame
        """
        dataframe['ema_fast'] = ta.EMA(dataframe, timeperiod=10)
        dataframe['ema_slow'] = ta.EMA(dataframe, timeperiod=25)
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)
        dataframe['plus_di'] = ta.PLUS_DI(dataframe, timeperiod=14)  # Bug修复: 添加DI指标
        dataframe['minus_di'] = ta.MINUS_DI(dataframe, timeperiod=14)
        dataframe['volume_ma'] = dataframe['volume'].rolling(20).mean()
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        
        price_change = (dataframe['close'] - dataframe['close'].shift(50)) / dataframe['close'].shift(50)
        dataframe['is_bull'] = price_change > 0.01
        
        return dataframe
    
    def _generate_trading_signals(self, dataframe: DataFrame) -> DataFrame:
        """生成交易信号
        
        基于多个条件的组合生成交易信号,并应用质量过滤。
        
        信号条件:
            - CCI交叉: CCI穿过阈值线
            - 价格位置: 价格相对于WMA的位置
            - EMA趋势: 快线和慢线的关系
            - ADX过滤: 趋势强度确认
            - 成交量过滤: 成交量放大确认
            - 质量过滤: 可靠度评分过滤
        
        Args:
            dataframe: 包含技术指标的DataFrame
            
        Returns:
            DataFrame: 添加signal_long和signal_short列的DataFrame
        """
        cci_prev = dataframe['active_cci'].shift(1)
        cci_cross_up = (
            (dataframe['active_cci'] > dataframe['active_cci_long']) & 
            (cci_prev <= dataframe['active_cci_long'])
        )
        cci_cross_down = (
            (dataframe['active_cci'] < dataframe['active_cci_short']) & 
            (cci_prev >= dataframe['active_cci_short'])
        )
        
        ema_trend_up = dataframe['ema_fast'] > dataframe['ema_slow']
        ema_trend_down = dataframe['ema_fast'] < dataframe['ema_slow']
        price_above_wma = dataframe['close'] > dataframe['active_wma']
        price_below_wma = dataframe['close'] < dataframe['active_wma']
        adx_filter = dataframe['adx'] > dataframe['active_adx']
        volume_filter = dataframe['volume'] > dataframe['volume_ma'] * dataframe['active_volume']
        
        # 简单质量过滤器：只过滤极低可靠度信号
        if self.enable_quality_filter and 'reliability_score' in dataframe.columns:
            quality_filter = dataframe['reliability_score'] >= self.min_reliability_score.value
        else:
            quality_filter = True
        
        dataframe['signal_long'] = (
            cci_cross_up & price_above_wma & ema_trend_up & adx_filter & volume_filter & quality_filter
        )
        
        dataframe['signal_short'] = (
            cci_cross_down & price_below_wma & ema_trend_down & 
            adx_filter & volume_filter & ~dataframe['is_bull'] & quality_filter
        )
        
        dataframe['rev_to_long'] = dataframe['signal_long']
        dataframe['rev_to_short'] = dataframe['signal_short']
        
        return dataframe
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """计算指标(主入口)
        
        Freqtrade框架调用的主入口函数,负责计算所有技术指标和信号。
        
        处理流程:
            1. 计算基础技术指标(EMA, ADX, ATR等)
            2. 识别市场结构(TREND/RANGE/BREAKOUT/CONTRACTION)
            3. 应用结构化参数(自适应CCI/WMA)
            4. 计算可靠度评分(0-100分)
            5. 生成交易信号(signal_long/signal_short)
        
        Args:
            dataframe: 包含OHLCV数据的DataFrame
            metadata: 交易对元数据
            
        Returns:
            DataFrame: 添加了所有指标和信号的DataFrame
        """
        dataframe = self._calculate_base_indicators(dataframe)
        dataframe = self.identify_market_structure(dataframe)
        dataframe = self.apply_structure_params(dataframe)
        dataframe = self._calculate_all_reliability_scores(dataframe)  # 添加可靠度计算
        dataframe = self._generate_trading_signals(dataframe)
        
        return dataframe
    
    # ========== 极端行情检测模块 ==========
    
    @staticmethod
    def _safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
        """安全除法工具函数
        
        避免除以零错误,在分母为0时返回默认值。
        
        Args:
            numerator: 分子
            denominator: 分母
            default: 分母为0时的默认返回值
            
        Returns:
            float: 计算结果或默认值
        """
        return numerator / denominator if denominator > 0 else default
    
    def _calculate_extreme_metrics(self, candle: Any) -> Tuple[float, float, float]:
        """计算极端行情度量指标
        
        计算用于判断极端行情的三个关键指标。
        
        Args:
            candle: 单根K线数据
            
        Returns:
            Tuple[float, float, float]: (波动率比率, 成交量比率, 价格变化)
        """
        volatility = candle.get('volatility', 0)
        volatility_ma = candle.get('volatility_ma', 0.003)
        volatility_ratio = self._safe_divide(volatility, volatility_ma, 1.0)
        
        volume_ratio = candle.get('volume_ratio', 1.0)
        
        high = candle.get('high', 0)
        low = candle.get('low', 0)
        close = candle.get('close', 0)
        price_change = self._safe_divide(abs(high - low), close, 0.0)
        
        return volatility_ratio, volume_ratio, price_change
    
    def detect_extreme_market(self, dataframe: DataFrame, index: int = -1) -> ExtremeMarketInfo:
        """检测极端行情
        
        识别市场是否处于极端状态,用于调整止损策略。
        
        检测三种极端情况:
            1. **波动率激增**: 当前波动率 > 均值 * 3
            2. **成交量暴涨**: 当前成交量 > 均值 * 5
            3. **快速价格变动**: 单根K线涨跌幅 > 5%
        
        Args:
            dataframe: 包含技术指标的DataFrame
            index: 要检测的K线索引(默认-1为最后一根)
            
        Returns:
            ExtremeMarketInfo: 极端行情信息
        """
        try:
            candle = dataframe.iloc[index]
            volatility_ratio, volume_ratio, price_change = self._calculate_extreme_metrics(candle)
            
            is_extreme_volatility = volatility_ratio > self.extreme_volatility_multiplier
            is_extreme_volume = volume_ratio > self.extreme_volume_multiplier
            is_extreme_price = price_change > self.extreme_price_change
            
            is_extreme = is_extreme_volatility or is_extreme_volume or is_extreme_price
            
            extreme_types = []
            intensity = 1.0
            
            if is_extreme_volatility:
                extreme_types.append('高波动')
                intensity = max(intensity, min(volatility_ratio / self.extreme_volatility_multiplier, 5.0))
            
            if is_extreme_volume:
                extreme_types.append('巨量')
                intensity = max(intensity, min(volume_ratio / self.extreme_volume_multiplier, 5.0))
            
            if is_extreme_price:
                extreme_types.append('急速变动')
                intensity = max(intensity, min(price_change / self.extreme_price_change, 5.0))
            
            extreme_type = '+'.join(extreme_types) if extreme_types else '正常'
            
            return ExtremeMarketInfo(
                is_extreme=is_extreme,
                extreme_type=extreme_type,
                intensity=intensity,
                volatility_ratio=volatility_ratio,
                volume_ratio=volume_ratio,
                price_change=price_change
            )
            
        except Exception:
            return ExtremeMarketInfo(
                is_extreme=False,
                extreme_type='正常',
                intensity=1.0,
                volatility_ratio=1.0,
                volume_ratio=1.0,
                price_change=0.0
            )

    def _get_extreme_info_cached(self, pair: str, dataframe: DataFrame) -> ExtremeMarketInfo:
        """缓存极端行情检测结果
        
        优化点:
        1. 使用LRU缓存替代手动清理
        2. 基于时间戳而非索引作为缓存键
        """
        if not hasattr(self, '_extreme_cache'):
            self._extreme_cache = {}
        
        # 使用时间戳作为缓存键,更可靠
        if len(dataframe) == 0:
            return ExtremeMarketInfo(False, '正常', 1.0, 1.0, 1.0, 0.0)
        
        last_candle = dataframe.iloc[-1]
        timestamp = last_candle.name if hasattr(last_candle.name, '__hash__') else str(last_candle.name)
        key = (pair, timestamp)
        
        if key in self._extreme_cache:
            return self._extreme_cache[key]
        
        info = self.detect_extreme_market(dataframe, -1)
        
        # 使用FIFO清理策略,保留最近的缓存
        if len(self._extreme_cache) > 200:
            # 删除最旧的100个条目
            old_keys = list(self._extreme_cache.keys())[:100]
            for old_key in old_keys:
                del self._extreme_cache[old_key]
        
        self._extreme_cache[key] = info
        return info
    
    def _get_bottom_info_cached(self, pair: str, dataframe: DataFrame, trade: Optional[Trade] = None) -> BottomStructureInfo:
        """缓存底部结构检测结果
        
        优化点:
        1. 使用时间戳替代索引
        2. FIFO清理策略
        3. 空DataFrame快速返回
        """
        if not hasattr(self, '_bottom_cache'):
            self._bottom_cache = {}
        
        if len(dataframe) == 0:
            return BottomStructureInfo.empty()
        
        # 使用时间戳作为缓存键
        last_candle = dataframe.iloc[-1]
        timestamp = last_candle.name if hasattr(last_candle.name, '__hash__') else str(last_candle.name)
        trade_id = getattr(trade, 'id', None) if trade is not None else None
        key = (pair, timestamp, trade_id)
        
        if key in self._bottom_cache:
            return self._bottom_cache[key]
        
        info = self.detect_bottom_structure(dataframe, trade)
        
        # FIFO清理策略
        if len(self._bottom_cache) > 200:
            old_keys = list(self._bottom_cache.keys())[:100]
            for old_key in old_keys:
                del self._bottom_cache[old_key]
        
        self._bottom_cache[key] = info
        return info
    
    # ========== 底部结构识别模块 ==========
    
    def detect_bottom_structure(self, dataframe: DataFrame, trade: Optional[Trade] = None) -> BottomStructureInfo:
        """检测底部结构（专为空单设计）
        
        识别四种底部形态：
        1. 吸筹底：放量但价格不涨
        2. 双底：多次下探但不破低
        3. 锤头线：长下影线+小实体
        4. 看涨吞没：大阳线吞没前阴线
        
        Returns:
            BottomStructureInfo: 底部结构信息
        """
        logger = logging.getLogger(__name__)
        
        try:
            if len(dataframe) < self.BOTTOM_LOOKBACK_CANDLES:
                return self._empty_bottom_info()
            
            recent = dataframe.tail(self.BOTTOM_LOOKBACK_CANDLES)
            current = recent.iloc[-1]
            prev = recent.iloc[-2]
            
            # === 1. 成交量吸筹检测 ===
            volume_accumulation = self._detect_volume_accumulation(recent, current)
            
            # === 2. 价格支撑检测 ===
            price_support = self._detect_price_support(recent, current, trade)
            
            # === 3. K线形态检测 ===
            candle_pattern, pattern_type = self._detect_bottom_candle_pattern(current, prev)
            
            # === 4. 反转前兆评分 ===
            reversal_score = self._calculate_reversal_score(
                recent, current, volume_accumulation, price_support, candle_pattern
            )
            
            # === 5. 综合判断 ===
            confirmed_signals = sum([volume_accumulation, price_support, candle_pattern])
            confidence = (confirmed_signals / 3.0) * 100
            
            # 如果反转评分高，提升置信度（使用Hyperopt参数）
            if reversal_score >= self.reversal_score_threshold.value:
                confidence = min(confidence * 1.2, 100)
            
            # 放宽判断条件：只需满足其一即可
            is_bottom = (
                confidence >= self.bottom_confidence_threshold.value or
                reversal_score >= self.reversal_score_threshold.value
            )
            
            if is_bottom:
                logger.info(
                    f"🎯 底部结构识别 [{pattern_type}]: "
                    f"置信度={confidence:.0f}% | 反转评分={reversal_score:.0f} | "
                    f"吸筹={volume_accumulation} | 支撑={price_support} | 形态={candle_pattern}"
                )
            
            return BottomStructureInfo(
                is_bottom=is_bottom,
                bottom_type=pattern_type,
                confidence=confidence,
                volume_accumulation=volume_accumulation,
                price_support=price_support,
                candle_pattern=candle_pattern,
                reversal_score=reversal_score
            )
            
        except Exception as e:
            logger.error(f"❌ 底部结构检测失败: {e}")
            return self._empty_bottom_info()
    
    def _empty_bottom_info(self) -> BottomStructureInfo:
        """返回空底部信息"""
        return BottomStructureInfo.empty()
    
    def _detect_volume_accumulation(self, recent: DataFrame, current: Any) -> bool:
        """检测成交量吸筹（放量但价格不涨）"""
        try:
            avg_volume = recent['volume'].tail(5).mean()
            current_volume = current['volume']
            volume_spike = current_volume > avg_volume * self.bottom_volume_accumulation.value
            
            body_size = abs(current['close'] - current['open'])
            candle_range = current['high'] - current['low']
            small_body = self._safe_divide(body_size, candle_range, 1.0) < 0.3
            
            return volume_spike and small_body
        except (KeyError, ValueError, TypeError) as e:
            self.logger.debug(f"成交量吸筹检测失败: {e}")
            return False
    
    def _detect_price_support(self, recent: DataFrame, current: Any, trade: Optional[Trade]) -> bool:
        """检测价格支撑（多次下探不破低）"""
        try:
            lows = recent['low'].values
            current_low = current['low']
            min_low = lows.min()
            
            distance_to_min = self._safe_divide(current_low - min_low, min_low, 0.0)
            tolerance = self.bottom_price_tolerance.value
            near_support = distance_to_min <= tolerance
            
            support_touches = sum(
                self._safe_divide(abs(low - min_low), min_low, 1.0) <= tolerance
                for low in lows
            )
            
            return near_support and support_touches >= 2
        except (KeyError, ValueError, TypeError, AttributeError) as e:
            self.logger.debug(f"价格支撑检测失败: {e}")
            return False
    
    def _detect_bottom_candle_pattern(self, current: Any, prev: Any) -> Tuple[bool, str]:
        """检测底部K线形态
        
        Returns:
            (是否检测到形态, 形态类型)
        """
        try:
            # === 1. 锤头线检测 ===
            body = abs(current['close'] - current['open'])
            lower_wick = min(current['open'], current['close']) - current['low']
            upper_wick = current['high'] - max(current['open'], current['close'])
            
            # 锤头线：长下影线 + 小实体 + 短上影线（使用Hyperopt参数）
            is_hammer = (
                lower_wick > body * self.bottom_hammer_wick_ratio.value and
                body > 0 and
                upper_wick < body * 0.5
            )
            
            if is_hammer:
                return True, '锤头线'
            
            # === 2. 看涨吞没检测 ===
            prev_body = abs(prev['close'] - prev['open'])
            prev_is_bearish = prev['close'] < prev['open']
            current_is_bullish = current['close'] > current['open']
            
            # 看涨吞没：大阳线完全吞没前一根阴线（使用Hyperopt参数）
            is_engulfing = (
                prev_is_bearish and
                current_is_bullish and
                body > prev_body * self.bottom_engulfing_body_ratio.value and
                current['close'] > prev['open'] and
                current['open'] < prev['close']
            )
            
            if is_engulfing:
                return True, '看涨吞没'
            
            # === 3. 十字星检测 ===
            candle_range = current['high'] - current['low']
            is_doji = body < candle_range * 0.1 if candle_range > 0 else False
            
            if is_doji:
                return True, '十字星'
            
            return False, '无'
            
        except (KeyError, ValueError, TypeError) as e:
            self.logger.debug(f"K线形态检测失败: {e}")
            return False, '无'
    
    def _calculate_reversal_score(self, recent: DataFrame, current: Any, 
                                   volume_acc: bool, price_sup: bool, pattern: bool) -> float:
        """计算反转前兆评分（0-100）
        
        综合考虑：
        1. 成交量变化（35%）
        2. 波动率压缩（25%）
        3. K线形态（40%）
        """
        try:
            # 1. 成交量评分
            avg_volume = recent['volume'].tail(10).mean()
            current_volume = current['volume']
            volume_ratio = self._safe_divide(current_volume, avg_volume, 1.0)
            volume_score = self._normalize_score(volume_ratio, 3.0)
            if volume_acc:
                volume_score = min(volume_score * 1.3, 100)
            
            # 2. 波动率评分
            atr = current.get('atr', 0.001)
            atr_ma = recent['atr'].tail(20).mean() if 'atr' in recent.columns else atr
            volatility_ratio = self._safe_divide(atr, atr_ma, 1.0)
            volatility_score = max(100 - (volatility_ratio - 1.0) * 100, 0)
            
            # 3. K线形态评分
            pattern_score = 100 if pattern else (70 if price_sup else 0)
            
            # 加权汇总
            score = (
                volume_score * self.reversal_volume_weight.value +
                volatility_score * self.reversal_volatility_weight.value +
                pattern_score * self.reversal_pattern_weight.value
            )
            
            return min(score, 100)
        except (KeyError, ValueError, TypeError, ZeroDivisionError) as e:
            self.logger.debug(f"反转评分计算失败: {e}")
            return 0.0
    
    # ========== 可靠度评分模块 ==========
    
    # 市场结构基础评分(根据历史表现设定)
    STRUCTURE_SCORES = {
        'BREAKOUT': 100,      # 突破: 最高质量
        'TREND': 85,          # 趋势: 高质量
        'CONTRACTION': 60,    # 收缩: 中等质量
        'RANGE': 40           # 震荡: 较低质量
    }
    
    def _score_structure(self, structure: str) -> float:
        """市场结构评分
        
        根据市场结构类型返回基础评分,并应用权重。
        
        Args:
            structure: 市场结构类型
            
        Returns:
            float: 加权后的评分
        """
        return self.STRUCTURE_SCORES.get(structure, 40) * self.reliability_weights['structure']
    
    @staticmethod
    def _normalize_score(value: float, max_value: float) -> float:
        """归一化评分到0-100
        
        将任意范围的数值线性映射到0-100区间。
        
        Args:
            value: 当前值
            max_value: 最大值(对应100分)
            
        Returns:
            float: 归一化后的评分(0-100)
        """
        return min(value / max_value * 100, 100) if max_value > 0 else 0.0
    
    def _score_trend_strength(self, candle: Any) -> float:
        """趋势强度评分"""
        trend_strength = candle.get('trend_strength', 0)
        adx = candle.get('adx', 0)
        
        trend_score = self._normalize_score(trend_strength, 0.05)
        adx_score = self._normalize_score(adx, 50)
        trend_combined = trend_score * 0.6 + adx_score * 0.4
        
        return trend_combined * self.reliability_weights['trend_strength']
    
    def _score_momentum(self, candle: Any) -> float:
        """动量指标评分"""
        cci = abs(candle.get('active_cci', 0))
        cci_threshold = abs(candle.get('active_cci_long', -50))
        cci_score = self._normalize_score(cci, cci_threshold * 2) if cci_threshold > 0 else 50
        return cci_score * self.reliability_weights['momentum']
    
    def _score_volume(self, candle: Any) -> float:
        """成交量评分"""
        volume_ratio = candle.get('volume_ratio', 1.0)
        volume_score = self._normalize_score(max(volume_ratio - 1, 0), 4)
        return volume_score * self.reliability_weights['volume']
    
    def _score_volatility(self, candle: Any) -> float:
        """波动率评分"""
        volatility = candle.get('volatility', 0)
        volatility_ma = candle.get('volatility_ma', 0.003)
        
        if volatility_ma > 0:
            vol_ratio = volatility / volatility_ma
            if 1.5 <= vol_ratio <= 2.5:
                vol_score = 100
            elif vol_ratio < 1.5:
                vol_score = vol_ratio / 1.5 * 100
            else:
                vol_score = max(100 - (vol_ratio - 2.5) * 20, 0)
        else:
            vol_score = 50
        
        return vol_score * self.reliability_weights['volatility']
    
    def _score_signal_quality(self, candle: Any) -> float:
        """信号质量评分"""
        ema_fast = candle.get('ema_fast', 0)
        ema_slow = candle.get('ema_slow', 0)
        close = candle.get('close', 0)
        
        if close > 0 and ema_fast > 0 and ema_slow > 0:
            if close > ema_fast > ema_slow or close < ema_fast < ema_slow:
                signal_score = 100
            elif (close > ema_fast) or (close < ema_fast):
                signal_score = 60
            else:
                signal_score = 30
        else:
            signal_score = 50
        
        return signal_score * self.reliability_weights['signal_quality']
    
    def calculate_reliability_score(self, dataframe: DataFrame, index: int) -> float:
        """计算订单可靠度评分
        
        综合多个维度评估交易信号的可靠性,用于动态调整杠杆和过滤低质量信号。
        
        评分维度和权重:
            1. **市场结构**(25%): BREAKOUT > TREND > CONTRACTION > RANGE
            2. **趋势强度**(20%): 基于价格变化率和ADX
            3. **动量指标**(20%): CCI强度和位置
            4. **成交量**(15%): 成交量比率
            5. **波动率**(10%): ATR相对值
            6. **信号质量**(10%): EMA趋势一致性
        
        Args:
            dataframe: 包含技术指标的DataFrame
            index: 要计算的K线索引
            
        Returns:
            float: 可靠度评分(0-100)
        """
        try:
            candle = dataframe.iloc[index]
            structure = candle.get('structure', 'RANGE')
            
            score = (
                self._score_structure(structure) +
                self._score_trend_strength(candle) +
                self._score_momentum(candle) +
                self._score_volume(candle) +
                self._score_volatility(candle) +
                self._score_signal_quality(candle)
            )
            
            return max(0, min(100, score))
            
        except Exception:
            return 0.0
    
    def get_leverage_from_reliability(self, reliability_score: float) -> float:
        """根据可靠度分数获取杠杆倍数
        
        Args:
            reliability_score: 可靠度评分（0-100）
            
        Returns:
            杠杆倍数（2-20倍）
            
        分级策略：
            - 高可靠度（>=80分）：20倍杠杆
            - 中可靠度（>=65分）：10倍杠杆
            - 低可靠度（>=50分）：5倍杠杆
            - 最低可靠度：2倍杠杆
        """
        if not self.use_dynamic_leverage:
            return self.min_leverage
        
        # 使用可优化的阈值和杠杆参数
        if reliability_score >= self.leverage_threshold_high.value:
            return self.leverage_high.value
        elif reliability_score >= self.leverage_threshold_mid.value:
            return self.leverage_mid.value
        elif reliability_score >= self.leverage_threshold_low.value:
            return self.leverage_low.value
        else:
            return self.leverage_min.value
    
    # ========== 入场/出场信号模块 ==========
    
    def _calculate_all_reliability_scores(self, dataframe: DataFrame) -> DataFrame:
        """计算所有行的可靠度分数"""
        dataframe['reliability_score'] = 0.0
        for i in range(len(dataframe)):
            if i >= self.startup_candle_count:
                dataframe.loc[dataframe.index[i], 'reliability_score'] = self.calculate_reliability_score(dataframe, i)
        return dataframe
    
    def _tag_entries(self, dataframe: DataFrame, mask, direction: str) -> DataFrame:
        """标记入场信号"""
        if mask.any():
            dataframe.loc[mask, f'enter_{direction}'] = 1
            for idx in dataframe[mask].index:
                structure = dataframe.loc[idx, 'structure']
                reliability = dataframe.loc[idx, 'reliability_score']
                leverage = self.get_leverage_from_reliability(reliability)
                dataframe.loc[idx, 'enter_tag'] = f'{direction}_{structure}_R{int(reliability)}_L{leverage}x'
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """入场信号 - 根据信号生成入场标记，并标注市场结构和可靠度"""
        # 可靠度已在populate_indicators中计算，这里直接使用
        dataframe = self._tag_entries(dataframe, dataframe['signal_long'], 'long')
        dataframe = self._tag_entries(dataframe, dataframe['signal_short'], 'short')
        return dataframe
    
    # ========== 价格优化模块 ==========
    
    def _get_limit_price_offset(self, atr: float, structure: str, offset_ratios: Dict[str, float]) -> float:
        """计算限价单偏移"""
        offset_ratio = offset_ratios.get(structure, 0.10)
        return atr * offset_ratio
    
    def custom_entry_price(self, pair: str, current_time: datetime, proposed_rate: float,
                          entry_tag: Optional[str], side: str, **kwargs) -> float:
        """限价单入场价格优化
        
        策略：
        - 做多：在当前价格下方挂单，等待回调入场
        - 做空：在当前价格上方挂单，等待反弹入场
        - 根据市场结构调整挂单距离
        """
        try:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if len(dataframe) == 0:
                return proposed_rate
            
            last_candle = dataframe.iloc[-1]
            atr = last_candle['atr']
            structure = last_candle.get('structure', 'RANGE')
            
            offset = self._get_limit_price_offset(atr, structure, self.ENTRY_OFFSET_RATIOS)
            
            return proposed_rate - offset if side == 'long' else proposed_rate + offset
                
        except Exception:
            pass
        
        return proposed_rate
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """退出信号 - 基于反转信号退出
        
        增强功能：
        1. 原有的趋势反转信号（rev_to_long/rev_to_short）
        2. 🎯 新增底部结构识别（专为空单设计）
        """
        logger = logging.getLogger(__name__)
        
        # === 原有反转信号 ===
        if dataframe['rev_to_short'].any():
            dataframe.loc[dataframe['rev_to_short'], 'exit_long'] = 1
            dataframe.loc[dataframe['rev_to_short'], 'exit_tag'] = 'reversal_to_short'
        
        if dataframe['rev_to_long'].any():
            dataframe.loc[dataframe['rev_to_long'], 'exit_short'] = 1
            dataframe.loc[dataframe['rev_to_long'], 'exit_tag'] = 'reversal_to_long'
        
        # === 🎯 新增：底部结构识别（空单专用） ===
        try:
            # 为每根K线检测底部结构（仅检测最近的K线以提高性能）
            if len(dataframe) >= self.BOTTOM_LOOKBACK_CANDLES:
                # 只检测最后一根K线（使用缓存）
                pair = metadata.get('pair', 'UNKNOWN')
                bottom_info = self._get_bottom_info_cached(pair, dataframe, None)
                
                if bottom_info.is_bottom:
                    # 标记为底部反转出场信号
                    dataframe.loc[dataframe.index[-1], 'exit_short'] = 1
                    dataframe.loc[dataframe.index[-1], 'exit_tag'] = f'bottom_{bottom_info.bottom_type}'
                    
                    logger.info(
                        f"🎯 底部出场信号 [{metadata.get('pair', 'UNKNOWN')}][{bottom_info.bottom_type}]: "
                        f"置信度={bottom_info.confidence:.0f}% | 反转评分={bottom_info.reversal_score:.0f}"
                    )
        
        except Exception as e:
            logger.error(f"❌ 底部结构检测失败: {e}")
        
        return dataframe
    
    def custom_exit_price(self, pair: str, trade: Trade, current_time: datetime,
                         proposed_rate: float, current_profit: float, exit_tag: Optional[str],
                         **kwargs) -> float:
        """限价单出场价格优化
        
        策略：
        - 反转信号/底部信号/亏损：立即限价出场
        - 盈利时：根据市场结构设置限价单，争取更好价格
        """
        try:
            # 🎯 底部反转信号或原有反转信号：立即限价出场
            if (exit_tag and ('reversal' in exit_tag or 'bottom' in exit_tag)) or current_profit < 0:
                return proposed_rate
            
            dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if len(dataframe) == 0:
                return proposed_rate
            
            last_candle = dataframe.iloc[-1]
            atr = last_candle['atr']
            structure = last_candle.get('structure', 'RANGE')
            
            offset = self._get_limit_price_offset(atr, structure, self.EXIT_OFFSET_RATIOS)
            
            return proposed_rate - offset if trade.is_short else proposed_rate + offset
                
        except Exception:
            pass
        
        return proposed_rate
    
    # ========== 智能止损系统：三维度升级 ==========
    
    def _calculate_volatility_metrics(self, dataframe: DataFrame) -> Dict[str, float]:
        """波动率自适应模块：计算多维度波动率指标
        
        返回：
        - atr: 平均真实波动幅度
        - stddev: 收盘价标准差
        - body_ratio: K线实体占比均值
        - volatility_score: 综合波动率评分（0-1）
        """
        atr = dataframe.iloc[-1].get('atr', 0.001)
        current_price = dataframe.iloc[-1]['close']
        
        # 标准差（归一化）
        closes = dataframe['close'].tail(self.volatility_stddev_period)
        stddev = closes.std() / current_price
        
        # K线实体占比（过滤十字星和长影线）
        recent_candles = dataframe.tail(10)
        body_sizes = abs(recent_candles['close'] - recent_candles['open'])
        total_ranges = recent_candles['high'] - recent_candles['low']
        body_ratios = body_sizes / total_ranges.replace(0, 1)
        body_ratio = body_ratios.mean()
        
        # 综合波动率评分（归一化到0-1）
        atr_normalized = min(atr / current_price / 0.01, 1.0)  # 假设1%为高波动
        stddev_normalized = min(stddev / 0.01, 1.0)
        body_normalized = body_ratio
        
        volatility_score = (atr_normalized * 0.5 + stddev_normalized * 0.3 + body_normalized * 0.2)
        
        return {
            'atr': atr,
            'stddev': stddev,
            'body_ratio': body_ratio,
            'volatility_score': volatility_score
        }
    
    def _check_behavior_confirmation(self, dataframe: DataFrame, trade: Trade, is_long: bool) -> Dict[str, Any]:
        """行为确认模块：验证止损触发是否为真实反转
        
        返回：
        - volume_confirmed: 成交量放大确认
        - support_broken: 支撑位突破确认
        - consecutive_reversal: 连续反向K线确认
        - should_trigger: 综合判断是否应触发止损
        """
        recent_candles = dataframe.tail(self.behavior_support_break_confirm + 1)
        
        # 1. 成交量确认
        current_volume = recent_candles.iloc[-1]['volume']
        avg_volume = recent_candles['volume'].iloc[:-1].mean()
        volume_confirmed = current_volume > avg_volume * self.behavior_volume_spike_threshold
        
        # 2. 支撑位突破确认
        entry_price = trade.open_rate
        price_threshold = self.BEHAVIOR_PRICE_BREAK_LONG if is_long else self.BEHAVIOR_PRICE_BREAK_SHORT
        breaks = (recent_candles['close'] < entry_price * price_threshold).sum() if is_long else \
                 (recent_candles['close'] > entry_price * price_threshold).sum()
        support_broken = breaks >= self.behavior_support_break_confirm
        
        # 3. 连续反向K线确认
        last_n_candles = recent_candles.tail(self.behavior_consecutive_candles)
        condition = (last_n_candles['close'] < last_n_candles['open']) if is_long else \
                   (last_n_candles['close'] > last_n_candles['open'])
        consecutive_reversal = condition.sum() >= self.behavior_consecutive_candles
        
        # 综合判断
        confirmations = sum([volume_confirmed, support_broken, consecutive_reversal])
        
        return {
            'volume_confirmed': volume_confirmed,
            'support_broken': support_broken,
            'consecutive_reversal': consecutive_reversal,
            'should_trigger': confirmations >= 2,
            'confirmation_count': confirmations
        }
    
    def _check_trend_continuation_guard(self, trade: Trade, dataframe: DataFrame, is_long: bool) -> Dict[str, bool]:
        """趋势延续保护模块：基于入场信号强度的保护机制
        
        增强版：添加方向确认，防止在正确方向上过早止损
        
        返回：
        - is_protected: 是否处于保护期
        - entry_reliability: 入场可靠度
        - candles_since_entry: 入场后K线数
        - reversal_confirmed: 反转是否确认
        - direction_confirmed: 方向是否持续正确
        """
        # 获取入场时的可靠度（从trade的tag中提取）
        entry_reliability = 0
        if hasattr(trade, 'entry_tag') and trade.entry_tag:
            # tag格式: "long_TREND_R75_L10.0x" 或 "short_RANGE_R55_L5.0x"
            # 提取R后面的数字作为可靠度
            import re
            match = re.search(r'_R(\d+)_', trade.entry_tag)
            if match:
                entry_reliability = int(match.group(1))
        
        # 备用：从trade属性获取
        if entry_reliability == 0:
            entry_reliability = getattr(trade, 'entry_reliability', 0)
        
        # 计算入场后K线数
        if not hasattr(trade, 'entry_candle_index'):
            trade.entry_candle_index = len(dataframe) - 1
        candles_since_entry = len(dataframe) - 1 - trade.entry_candle_index
        
        # 降低保护期门槛：可靠度≥50（原来65）
        is_protected = (
            entry_reliability >= 50 and
            candles_since_entry <= self.trend_guard_candles
        )
        
        # 方向确认检查（简化版 - 只看价格方向）
        direction_confirmed = False
        if is_protected and candles_since_entry >= 3:  # 至少3根K线后才判断
            current_price = dataframe.iloc[-1]['close']
            entry_price = trade.open_rate
            
            if is_long:
                # 做多：价格未跌破入场价3%，认为方向正确
                direction_confirmed = current_price > entry_price * 0.97
            else:
                # 做空：价格未涨破入场价3%，认为方向正确
                direction_confirmed = current_price < entry_price * 1.03
        
        # 反转确认：连续N根强反向K线
        if is_protected:
            recent_candles = dataframe.tail(self.trend_guard_reversal_confirm)
            if is_long:
                # 做多：检查是否连续大阴线
                bearish_candles = (recent_candles['close'] < recent_candles['open']).sum()
                strong_bearish = ((recent_candles['open'] - recent_candles['close']) / recent_candles['open'] > self.TREND_GUARD_STRONG_MOVE).sum()
                reversal_confirmed = bearish_candles >= self.trend_guard_reversal_confirm and strong_bearish >= 2
            else:
                # 做空：检查是否连续大阳线
                bullish_candles = (recent_candles['close'] > recent_candles['open']).sum()
                strong_bullish = ((recent_candles['close'] - recent_candles['open']) / recent_candles['open'] > self.TREND_GUARD_STRONG_MOVE).sum()
                reversal_confirmed = bullish_candles >= self.trend_guard_reversal_confirm and strong_bullish >= 2
        else:
            reversal_confirmed = True  # 不在保护期，默认确认
        
        return {
            'is_protected': is_protected,
            'entry_reliability': entry_reliability,
            'candles_since_entry': candles_since_entry,
            'reversal_confirmed': reversal_confirmed,
            'direction_confirmed': direction_confirmed
        }
    
    def _calculate_base_stoploss(self, dataframe: DataFrame, structure: str, volatility_metrics: Dict[str, float]) -> float:
        """计算基础止损（波动率自适应 + 市场结构）
        
        升级点：
        1. 引入标准差和K线实体分析
        2. 根据综合波动率动态调整ATR倍数
        3. 低实体占比（十字星）时放宽止损
        """
        atr = volatility_metrics['atr']
        current_price = dataframe.iloc[-1]['close']
        volatility_score = volatility_metrics['volatility_score']
        body_ratio = volatility_metrics['body_ratio']
        
        # 基础倍数（从市场结构获取）
        base_multipliers = {
            'TREND': self.stoploss_atr_multiplier_trend.value,
            'RANGE': self.stoploss_atr_multiplier_range.value,
            'BREAKOUT': self.stoploss_atr_multiplier_breakout.value,
            'CONTRACTION': self.stoploss_atr_multiplier_contraction.value
        }
        base_multiplier = base_multipliers.get(structure, 2.0)
        
        # 波动率自适应调整：高波动时放宽，低波动时收紧
        adaptive_multiplier = base_multiplier * (1 + (volatility_score - 0.5) * self.volatility_adaptive_multiplier.value)
        
        # 低实体占比保护（十字星/长影线）：放宽30%
        if body_ratio < self.volatility_body_ratio_min:
            adaptive_multiplier *= 1.3
        
        stoploss_distance = (atr * adaptive_multiplier) / current_price
        
        # 限制在合理范围内
        return max(min(-stoploss_distance, self.STOPLOSS_MAX), self.STOPLOSS_MIN)
    
    def _detect_wick(self, candle: Any) -> bool:
        """检测插针K线
        
        插针特征：上影线或下影线占K线总长度>60%
        """
        if not self.wick_protection_enabled:
            return False
        
        high = candle['high']
        low = candle['low']
        open_price = candle['open']
        close = candle['close']
        
        total_range = high - low
        if total_range == 0:
            return False
        
        upper_wick = high - max(open_price, close)
        lower_wick = min(open_price, close) - low
        
        upper_wick_ratio = upper_wick / total_range
        lower_wick_ratio = lower_wick / total_range
        
        return (upper_wick_ratio > self.WICK_RATIO_THRESHOLD or 
                lower_wick_ratio > self.WICK_RATIO_THRESHOLD)
    
    def _get_breakeven_threshold(self, structure: str, is_extreme: bool) -> float:
        """获取保本阈值
        
        根据市场结构和极端行情动态调整保本触发点：
        - 极端行情: 2.7% - 快速保护
        - CONTRACTION: 1.7% - 低波动，快速保本
        - RANGE: 2.2% - 中等波动
        - TREND: 2.5% - 给趋势发展空间
        - BREAKOUT: 3.3% - 给突破确认空间
        """
        if is_extreme:
            return self.breakeven_extreme.value
        
        thresholds = {
            'TREND': self.breakeven_trend.value,
            'RANGE': self.breakeven_range.value,
            'BREAKOUT': self.breakeven_breakout.value,
            'CONTRACTION': self.breakeven_contraction.value
        }
        
        return thresholds.get(structure, self.breakeven_range.value)
    
    def _calculate_dynamic_protection_ratio(self, dataframe: DataFrame, trade: Trade, current_time: datetime) -> float:
        """[已弃用] 计算智能动态保护比例（三维度：趋势强度 + 波动率 + 持仓时间）
        
        ⚠️ 此函数已被新版止盈止损系统替代，仅保留用于兼容性
        返回值：保护比例（0.70-0.95），数值越小允许回撤越大
        """
        # 1. 趋势强度维度
        current_candle = dataframe.iloc[-1]
        adx = current_candle.get('adx', 20)
        plus_di = current_candle.get('plus_di', 20)
        minus_di = current_candle.get('minus_di', 20)
        
        # 计算趋势强度（0-1）
        trend_strength = 0.5
        # Bug修复: 确保DI指标有效（不是默认值）
        if adx > 25 and plus_di is not None and minus_di is not None:
            di_diff = abs(plus_di - minus_di)
            trend_strength = min((adx / 50) * (di_diff / 50), 1.0)
        
        # 趋势强度自适应
        if trend_strength >= self.trend_strength_threshold_high.value:
            trend_ratio = self.trailing_trend_strong_ratio.value  # 强趋势：宽松
        else:
            trend_ratio = self.trailing_trend_weak_ratio.value    # 弱趋势：收紧
        
        # 2. 波动率维度
        atr = current_candle.get('atr', 0.01)
        current_price = current_candle['close']
        volatility = atr / current_price if current_price > 0 else 0.01
        
        # 波动率自适应
        if volatility >= self.volatility_threshold_high.value:
            volatility_ratio = self.trailing_volatility_high_ratio.value  # 高波动：宽松
        else:
            volatility_ratio = self.trailing_volatility_low_ratio.value   # 低波动：收紧
        
        # 3. 持仓时间维度
        # Bug修复: 统一使用 open_date_utc，并添加容错
        open_time = getattr(trade, 'open_date_utc', None) or trade.open_date
        hours_held = (current_time - open_time).total_seconds() / 3600
        
        if hours_held < self.time_threshold_mid.value:
            time_ratio = self.trailing_time_new_ratio.value      # 新仓位：宽松
        elif hours_held < self.time_threshold_old.value:
            time_ratio = self.trailing_time_mid_ratio.value      # 中期：适中
        else:
            time_ratio = self.trailing_time_old_ratio.value      # 老仓位：收紧
        
        # 综合三个维度（加权平均）
        # 趋势强度权重40%，波动率权重35%，时间权重25%
        final_ratio = (trend_ratio * 0.40 + volatility_ratio * 0.35 + time_ratio * 0.25)
        
        return final_ratio
    
    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                       current_rate: float, current_profit: float, **kwargs) -> float:
        """🎯 简化止盈止损系统 - 基于最高利润直接设置限价止损
        
        核心特性：
            1. **无状态设计**：直接使用trade.max_profit_ratio，无需额外缓存
            2. **分段式止盈**：保本 → 小利润 → 大利润
            3. **底部识别**：空单检测底部结构，盈利时立即平仓
            4. **极端行情保护**：特殊市场环境放宽止损
        
        Args:
            pair: 交易对
            trade: 交易对象
            current_time: 当前时间
            current_rate: 当前价格
            current_profit: 当前利润
            
        Returns:
            float: 止损位（负数表示止损，0表示保本，正数表示止盈）
        """
        logger = logging.getLogger(__name__)
        
        try:
            # 获取市场数据
            dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if len(dataframe) == 0:
                return self.DEFAULT_STOPLOSS
            
            current_candle = dataframe.iloc[-1]
            structure = current_candle.get('structure', 'RANGE')
            
            # ========== 🎯 空单底部结构识别 ==========
            if trade.is_short:
                bottom_info = self._get_bottom_info_cached(pair, dataframe, trade)
                if bottom_info.is_bottom:
                    # 盈利时：立即平仓，锁定利润
                    if current_profit > 0:
                        logger.warning(
                            f"🚨 底部识别-盈利平仓 [{pair}][{bottom_info.bottom_type}]: "
                            f"置信度={bottom_info.confidence:.0f}% | 利润={current_profit:.2%} → 立即平仓"
                        )
                        return 0.001  # 强制触发止盈
                    # 亏损时：放宽止损，等待反转确认
                    elif current_profit < 0 and bottom_info.confidence >= 60:
                        logger.warning(
                            f"🛡️ 底部识别-亏损保护 [{pair}][{bottom_info.bottom_type}]: "
                            f"置信度={bottom_info.confidence:.0f}% | 亏损={current_profit:.2%} → 暂不止损"
                        )
                        return -0.50  # 允许最多50%亏损，等待反转
            
            # 检测极端行情
            extreme_info = self._get_extreme_info_cached(pair, dataframe)
            is_extreme = extreme_info.is_extreme
            
            # === 直接使用trade.max_profit_ratio跟踪最高利润 ===
            max_profit = getattr(trade, 'max_profit_ratio', current_profit)
            
            if is_extreme:
                logger.info(f"⚡ 极端行情 [{pair}]: {extreme_info.extreme_type}, 强度={extreme_info.intensity:.2f}x")
            
            # ========== 分段式止盈系统 ==========
            
            # 1. 保本区间：达到阈值后移动到0
            breakeven_threshold = self._get_breakeven_threshold(structure, is_extreme)
            if max_profit >= breakeven_threshold:
                logger.info(
                    f"💰 保本止损 [{structure}{'|极端' if is_extreme else ''}]: "
                    f"阈值={breakeven_threshold:.2%}, 当前={current_profit:.2%}, 最高={max_profit:.2%}"
                )
                return 0.0
            
            # 2. 小利润区间：保护比例可优化（默认85%）
            if self.small_profit_threshold_min.value <= max_profit < self.profit_threshold_small:
                target = self.PROFIT_TARGETS.get(structure, 0.014) * self.profit_target_multiplier.value
                if max_profit >= target:
                    # 空单特殊处理：检测底部
                    if trade.is_short:
                        bottom_info = self._get_bottom_info_cached(pair, dataframe, trade)
                        if bottom_info.is_bottom and bottom_info.confidence >= self.bottom_confidence_exit_threshold.value:
                            logger.warning(
                                f"⚠️ 小利润区间检测到底部 [{pair}][{bottom_info.bottom_type}]: "
                                f"置信度={bottom_info.confidence:.0f}% | 利润={current_profit:.2%} → 取消止盈"
                            )
                            # 不设置止盈，让利润继续发展
                            return self.DEFAULT_STOPLOSS
                    
                    # 正常止盈：保护比例可优化
                    protection_ratio = self.small_profit_protection_ratio.value
                    trailing_stop = max_profit * protection_ratio
                    logger.info(
                        f"🔒 小利润锁定 [{structure}]: 保护{protection_ratio:.1%} | "
                        f"当前={current_profit:.2%}, 最高={max_profit:.2%} → 止损={trailing_stop:.2%}"
                    )
                    return trailing_stop
            
            # 3. 大利润区间：使用指数函数动态计算（>5%）参数可优化
            if max_profit >= self.profit_threshold_small:
                # 指数保护曲线：protection = base + (max - base) * (1 - exp(-k * profit))
                base_protection = self.large_profit_base_protection.value
                max_protection = self.large_profit_max_protection.value
                k = self.large_profit_curve_steepness.value
                protection_ratio = base_protection + (max_protection - base_protection) * (
                    1 - math.exp(-k * max_profit)
                )
                trailing_stop = max_profit * protection_ratio
                
                profit_level = "大额" if max_profit >= 0.5 else "中等"
                logger.info(
                    f"📈 {profit_level}利润追踪 [{pair}]: 保护{protection_ratio:.1%} | "
                    f"当前={current_profit:.2%}, 最高={max_profit:.2%} → 止损={trailing_stop:.2%}"
                )
                return trailing_stop
            
            # ========== 基础止损系统（亏损区间）==========
            
            # 计算基础止损
            volatility_metrics = self._calculate_volatility_metrics(dataframe)
            base_stoploss = self._calculate_base_stoploss(dataframe, structure, volatility_metrics)
            
            # ========== 🎯 重构后的自适应保护系统 ==========
            
            # 获取交易基础信息
            if not hasattr(trade, 'entry_candle_index'):
                trade.entry_candle_index = len(dataframe) - 1
            candles_since_entry = len(dataframe) - 1 - trade.entry_candle_index
            
            current_price = dataframe.iloc[-1]['close']
            entry_price = trade.open_rate
            is_long = not trade.is_short
            
            # 计算价格偏离度
            if is_long:
                price_deviation = (current_price - entry_price) / entry_price
            else:
                price_deviation = (entry_price - current_price) / entry_price
            
            # === 1. 新仓位保护（可优化参数）===
            if candles_since_entry <= self.new_position_candles.value:
                # 新仓位给予宽松止损,避免过早止损
                if price_deviation >= self.new_position_loss_threshold_1.value:  # 默认: 亏损<2%
                    new_position_multiplier = self.new_position_multiplier_low.value  # 默认: 2.5x
                elif price_deviation >= self.new_position_loss_threshold_2.value:  # 默认: 亏损2-5%
                    new_position_multiplier = self.new_position_multiplier_mid.value  # 默认: 1.8x
                else:  # 亏损>5%
                    new_position_multiplier = self.new_position_multiplier_high.value  # 默认: 1.2x
                
                base_stoploss = base_stoploss * new_position_multiplier
                logger.info(
                    f"🆕 新仓保护 [{pair}]: K线={candles_since_entry}/{self.new_position_candles.value}, "
                    f"偏离={price_deviation:.2%}, 倍数={new_position_multiplier:.1f}x → {base_stoploss:.2%}"
                )
            
            # === 2. 插针保护（可优化参数）===
            if self._detect_wick(current_candle):
                wick_adjusted = base_stoploss * self.wick_protection_multiplier.value
                logger.info(f"📍 插针保护 [{pair}]: {base_stoploss:.2%} → {wick_adjusted:.2%}")
                base_stoploss = wick_adjusted
            
            # === 3. 极端行情保护（可优化参数）===
            if is_extreme:
                extreme_adjusted = base_stoploss * self.extreme_protection_multiplier.value
                logger.info(f"⚡ 极端保护 [{pair}][{extreme_info.extreme_type}]: {base_stoploss:.2%} → {extreme_adjusted:.2%}")
                base_stoploss = extreme_adjusted
            
            # === 4. 行为确认保护（可优化参数）===
            if current_profit < base_stoploss * self.behavior_check_threshold.value:
                behavior_check = self._check_behavior_confirmation(dataframe, trade, is_long)
                
                if not behavior_check['should_trigger']:
                    relaxed_stoploss = base_stoploss * self.behavior_protection_multiplier.value
                    logger.info(
                        f"🛡️ 行为保护 [{pair}]: 确认度{behavior_check['confirmation_count']}/3 不足 → {relaxed_stoploss:.2%}"
                    )
                    base_stoploss = relaxed_stoploss
            
            return base_stoploss
                
        except Exception as e:
            logger.error(f"❌ 止损计算失败 [{pair}]: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return self.DEFAULT_STOPLOSS
    
    # ========== 仓位管理模块 ==========
    
    def _try_add_position(self, trade: Trade, current_profit: float, wallet_balance: float, structure: str) -> Optional[float]:
        """尝试加仓"""
        if structure not in ['TREND', 'BREAKOUT']:
            return None
        
        if not hasattr(trade, 'add_count'):
            trade.add_count = 0
        
        if current_profit >= self.dca_profit_1 and trade.add_count == 0:
            trade.add_count = 1
            return wallet_balance * self.dca_amount_1
        
        if current_profit >= self.dca_profit_2 and trade.add_count == 1:
            trade.add_count = 2
            return wallet_balance * self.dca_amount_2
        
        return None
    
    def _try_reduce_position(self, trade: Trade, current_profit: float) -> Optional[float]:
        """尝试减仓"""
        if current_profit <= self.DCA_REDUCE_THRESHOLD_1 and not hasattr(trade, 'reduced_1'):
            trade.reduced_1 = True
            return -trade.stake_amount * self.DCA_REDUCE_RATIO_1
        
        if current_profit <= self.DCA_REDUCE_THRESHOLD_2 and hasattr(trade, 'reduced_1') and not hasattr(trade, 'reduced_2'):
            trade.reduced_2 = True
            return -trade.stake_amount * self.DCA_REDUCE_RATIO_2
        
        return None
    
    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                             current_rate: float, current_profit: float,
                             min_stake: Optional[float], max_stake: float,
                             current_entry_rate: float, current_exit_rate: float,
                             current_entry_profit: float, current_exit_profit: float,
                             **kwargs) -> Optional[float]:
        """动态仓位调整
        
        Args:
            trade: 交易对象
            current_time: 当前时间
            current_rate: 当前价格
            current_profit: 当前利润
            min_stake: 最小仓位
            max_stake: 最大仓位
            current_entry_rate: 当前入场价
            current_exit_rate: 当前出场价
            current_entry_profit: 当前入场利润
            current_exit_profit: 当前出场利润
            
        Returns:
            调整金额（正数加仓，负数减仓）或None
        
        策略：
            1. 加仓：仅在TREND/BREAKOUT高质量交易中
            2. 减仓：所有交易均可减仓
        """
        try:
            wallet_balance = self.wallets.get_total_stake_amount()
            dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
            
            if len(dataframe) == 0:
                return None
            
            structure = dataframe.iloc[-1].get('structure', 'RANGE')
            
            # 尝试加仓
            add_amount = self._try_add_position(trade, current_profit, wallet_balance, structure)
            if add_amount is not None:
                return add_amount
            
            # 尝试减仓
            reduce_amount = self._try_reduce_position(trade, current_profit)
            if reduce_amount is not None:
                return reduce_amount
                    
        except Exception:
            pass
        
        return None
    
    # ========== 杠杆管理模块 ==========
    
    def _parse_reliability_from_tag(self, entry_tag: str) -> Optional[float]:
        """从entry_tag中解析可靠度分数"""
        if entry_tag and '_R' in entry_tag and '_L' in entry_tag:
            match = re.search(r'_R(\d+)_L', entry_tag)
            if match:
                return float(match.group(1))
        return None
    
    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                proposed_leverage: float, max_leverage: float, entry_tag: Optional[str],
                side: str, **kwargs) -> float:
        """动态杠杆计算 - 根据订单可靠度动态返回1-5倍杠杆"""
        logger = logging.getLogger(__name__)
        logger.info(f"🔧 leverage() 被调用 - pair={pair}, entry_tag={entry_tag}")
        
        try:
            # 从entry_tag解析可靠度
            reliability_score = self._parse_reliability_from_tag(entry_tag)
            
            # 如果解析失败，从 dataframe 获取
            if reliability_score is None:
                dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
                if len(dataframe) > 0:
                    reliability_score = dataframe.iloc[-1].get('reliability_score', 0)
            
            if reliability_score is not None:
                calculated_leverage = self.get_leverage_from_reliability(reliability_score)
                final_leverage = min(calculated_leverage, max_leverage)
                
                logger.info(f"🎯 智能杠杆 [{pair}]: 可靠度={reliability_score:.0f}分, 杠杆={final_leverage}x")
                return final_leverage
                
        except Exception as e:
            logger.error(f"❌ 智能杠杆计算失败 [{pair}]: {e}")
        
        logger.warning(f"⚠️ 使用默认杠杆 [{pair}]: {self.min_leverage}x")
        return self.min_leverage
    
    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                           time_in_force: str, current_time: datetime, entry_tag: Optional[str],
                           side: str, **kwargs) -> bool:
        """确认入场并保存可靠度分数（用于趋势延续保护）"""
        try:
            # 从entry_tag解析可靠度
            reliability_score = self._parse_reliability_from_tag(entry_tag)
            
            # 如果解析失败，从dataframe获取
            if reliability_score is None:
                dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
                if len(dataframe) > 0:
                    reliability_score = dataframe.iloc[-1].get('reliability_score', 0)
            
            # 保存到kwargs中，稍后会被trade对象接收
            if 'trade' in kwargs:
                trade = kwargs['trade']
                trade.entry_reliability = reliability_score if reliability_score else 0
                
        except Exception:
            pass
        
        return True
    
    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                           proposed_stake: float, min_stake: Optional[float], max_stake: float,
                           leverage: float, entry_tag: Optional[str], side: str,
                           **kwargs) -> float:
        """仓位管理 - 动态初始仓位: 1/(max_open_trades+2)，最大可达90%"""
        try:
            # 动态计算初始仓位: 1/(max_open_trades + 2)
            # 例如: max_open_trades=3 → 1/5 = 20%
            #      max_open_trades=5 → 1/7 = 14.3%
            max_open_trades = self.config.get('max_open_trades', 3)
            initial_position_ratio = 1.0 / (max_open_trades + 2)
            
            total_balance = self.wallets.get_total_stake_amount()
            stake_amount = total_balance * initial_position_ratio
            min_allowed = min_stake if min_stake else 0
            return max(min_allowed, min(stake_amount, max_stake))
        except Exception:
            return proposed_stake
