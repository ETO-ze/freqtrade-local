# Strategy Debug Lab

本地策略调试小面板，专门给 `AlternativeHunter` 这类“模型驱动运行时策略”用。

## 功能

- 查看当前 `model_runtime_policy.json`
- 查看每个币的：
  - `decision`
  - `direction_bias`
  - `stake_scale`
  - `leverage_cap`
  - `model_score / recent_model_score`
- 查看当前 stable 最优模型和 top factors
- 细调权重：
  - `stake_weight`
  - `leverage_weight`
  - `same_side_recent_boost`
  - `same_side_bias_multiplier`
  - `opposite_side_penalty`
  - `opposite_side_recent_penalty`
  - `bias_block_threshold`
  - `recent_weight_block_threshold`
  - `minimum_side_multiplier`
- 生成临时回测配置
- 生成临时 debug policy，不影响 live bot
- 一键跑 `AlternativeHunter` 回测
- 展示最新回测摘要和分币结果

## 启动

```powershell
cd C:\Users\Administrator\Documents\Playground\freqtrade-local
py -m streamlit run C:\Users\Administrator\Documents\Playground\freqtrade-local\strategy_debug_lab.py --server.address 127.0.0.1 --server.port 8502
```

或双击：

`C:\Users\Administrator\Documents\Playground\freqtrade-local\Launch Strategy Debug Lab.cmd`

打开：

[http://127.0.0.1:8502](http://127.0.0.1:8502)

## 关键文件

- 面板脚本：
  - `C:\Users\Administrator\Documents\Playground\freqtrade-local\strategy_debug_lab.py`
- 运行时策略：
  - `C:\Users\Administrator\Documents\Playground\freqtrade-local\user_data\model_runtime_policy.json`
- 默认回测配置：
  - `C:\Users\Administrator\Documents\Playground\freqtrade-local\user_data\config.backtest.alternativehunter.json`
- 临时回测配置：
  - `C:\Users\Administrator\Documents\Playground\freqtrade-local\user_data\config.backtest.strategylab.json`
- 临时 debug policy：
  - `C:\Users\Administrator\Documents\Playground\freqtrade-local\user_data\model_runtime_policy.debug.json`

## 说明

- 这个面板不会改动 live bot 配置。
- 它只生成独立的临时 backtest config 和 debug policy。
- 回测结果仍然落在：
  - `C:\Users\Administrator\Documents\Playground\freqtrade-local\user_data\backtest_results`
