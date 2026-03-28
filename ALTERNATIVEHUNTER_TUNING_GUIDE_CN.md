# AlternativeHunter 调参说明

## 用途

这个文件说明 `AlternativeHunter` 在策略调试面板里的可调参数。

相关文件：

- 策略：
  - `C:\Users\Administrator\Documents\Playground\freqtrade-local\user_data\strategies\AlternativeHunter.py`
- 调试面板：
  - `C:\Users\Administrator\Documents\Playground\freqtrade-local\strategy_debug_lab.py`
- 运行时策略：
  - `C:\Users\Administrator\Documents\Playground\freqtrade-local\user_data\model_runtime_policy.json`
- 调试临时策略：
  - `C:\Users\Administrator\Documents\Playground\freqtrade-local\user_data\model_runtime_policy.debug.json`

## 基础字段

这些字段来自 OpenClaw 的 stable 模型输出，不是手工输入。

### `decision`

- `tradable`：允许交易
- `observe`：观察
- `pause`：暂停

### `direction_bias`

- `long`：偏做多
- `short`：偏做空
- `both`：双向都可

### `model_score`

全样本模型综合分。越高通常说明该币整体质量越高。

### `recent_model_score`

近期模型分。越高说明最近这段时间更值得重视。

### `stake_scale`

币种基础仓位倍率。

常见含义：

- `1.0`：正常
- `0.75`：缩仓
- `0.5`：半仓
- `0`：基本禁用

### `leverage_cap`

该币允许的最大杠杆上限。

### `bias_strength`

方向偏置强度。越高说明模型对做多或做空的偏好越明确。

### `recent_weight`

近期因子权重。越高说明最近表现应当被更强地纳入决策。

## 可调参数

这些参数在调试面板里修改，只影响调试回测，不影响 live bot。

### `stake_weight`

控制模型偏置对仓位大小的影响强度。

- `0`：不根据模型调整仓位
- `1`：按当前默认逻辑调整
- `>1`：高置信币更重，低置信币更轻

建议范围：

- 稳健：`0.6 - 1.0`
- 激进：`1.1 - 1.5`

### `leverage_weight`

控制模型偏置对杠杆大小的影响强度。

- `0`：不根据模型调整杠杆
- `1`：默认强度
- `>1`：高置信方向杠杆更高，低置信方向更低

建议范围：

- 稳健：`0.5 - 1.0`
- 激进：`1.0 - 1.4`

### `same_side_recent_boost`

当模型方向和开仓方向一致时，`recent_weight` 带来的放大系数。

值越大，近期表现强的币放大越明显。

建议范围：

- `0.3 - 0.7`

### `same_side_bias_multiplier`

当模型方向和开仓方向一致时，`bias_strength` 的放大倍率。

值越大，方向明确的币会被更强放大。

建议范围：

- `2.0 - 5.0`

### `opposite_side_penalty`

当开仓方向和模型偏置相反时，直接扣减的惩罚值。

值越大，逆着模型方向开仓越难。

建议范围：

- `0.3 - 0.6`

### `opposite_side_recent_penalty`

当开仓方向与模型偏置相反时，近期权重额外带来的惩罚。

值越大，逆着近期方向开仓越难。

建议范围：

- `0.1 - 0.3`

### `bias_block_threshold`

当 `bias_strength` 达到这个阈值时，允许直接封掉反方向开仓。

值越低，越容易封边。

建议范围：

- `0.010 - 0.020`

### `recent_weight_block_threshold`

当 `recent_weight` 达到这个阈值时，允许仅根据近期信号封掉反方向。

值越低，近期走势的优先级越高。

建议范围：

- `0.35 - 0.55`

### `minimum_side_multiplier`

单边最小保底倍率。

即使被惩罚，也不会低于这个值。

建议范围：

- `0.05 - 0.15`

## 参数作用位置

### 开仓过滤

函数：

- `confirm_trade_entry()`

主要受这些参数影响：

- `bias_block_threshold`
- `recent_weight_block_threshold`
- `direction_bias`
- `bias_strength`
- `recent_weight`

### 仓位大小

函数：

- `custom_stake_amount()`

主要受这些参数影响：

- `stake_weight`
- `stake_scale`
- `same_side_recent_boost`
- `same_side_bias_multiplier`
- `opposite_side_penalty`

### 杠杆大小

函数：

- `leverage()`

主要受这些参数影响：

- `leverage_weight`
- `leverage_cap`
- 方向偏置相关参数

## 推荐起步参数

如果要做一组偏稳的测试，可以先试：

```text
stake_weight = 0.9
leverage_weight = 0.7
same_side_recent_boost = 0.45
same_side_bias_multiplier = 3.5
opposite_side_penalty = 0.55
opposite_side_recent_penalty = 0.25
bias_block_threshold = 0.012
recent_weight_block_threshold = 0.40
minimum_side_multiplier = 0.08
```

这组的特点：

- 更偏顺势
- 反向单更容易被压缩
- 杠杆比默认更保守

## 说明

- 面板里的调参只影响调试回测。
- live bot 不读取这份临时调试参数。
- 调试结果仍然写入：
  - `C:\Users\Administrator\Documents\Playground\freqtrade-local\user_data\backtest_results`
