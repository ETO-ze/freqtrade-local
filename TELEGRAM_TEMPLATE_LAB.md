# Telegram Template Lab

用于编辑 `OpenClaw` Telegram 消息模板，并基于当前 stable 报告做预览和测试发送。

## 功能

- 编辑本地模板文件
- 预览当前 stable 数据渲染后的消息
- 查看可用占位符
- 向 live Telegram 配置发送测试消息
- 向 sim Telegram 配置发送测试消息

## 启动

```powershell
cd C:\Users\Administrator\Documents\Playground\freqtrade-local
py -m streamlit run C:\Users\Administrator\Documents\Playground\freqtrade-local\telegram_template_lab.py --server.address 127.0.0.1 --server.port 8503
```

或双击：

`C:\Users\Administrator\Documents\Playground\freqtrade-local\Launch Telegram Template Lab.cmd`

打开：

[http://127.0.0.1:8503](http://127.0.0.1:8503)

## 相关文件

- 面板：`C:\Users\Administrator\Documents\Playground\freqtrade-local\telegram_template_lab.py`
- 模板：`C:\Users\Administrator\Documents\Playground\freqtrade-local\telegram_message_template.json`
- live Telegram 配置：`C:\Users\Administrator\Documents\Playground\freqtrade-local\openclaw.notification.json`
- sim Telegram 配置：`C:\Users\Administrator\Documents\Playground\freqtrade-local\openclaw.notification.sim.json`

## 模板占位符

- `{{generated_at}}`
- `{{strategy_name}}`
- `{{models}}`
- `{{best_model_name}}`
- `{{best_model_weight}}`
- `{{candidate_profit_pct}}`
- `{{candidate_profit_factor}}`
- `{{candidate_drawdown_pct}}`
- `{{candidate_trades}}`
- `{{tradable_pairs}}`
- `{{observe_pairs}}`
- `{{pause_pairs}}`
- `{{combined_report_path}}`
