# Telegram Template Lab

鐢ㄤ簬缂栬緫 `OpenClaw` Telegram 娑堟伅妯℃澘锛屽苟鍩轰簬褰撳墠 stable 鎶ュ憡鍋氶瑙堝拰娴嬭瘯鍙戦€併€?

## 鍔熻兘

- 缂栬緫鏈湴妯℃澘鏂囦欢
- 棰勮褰撳墠 stable 鏁版嵁娓叉煋鍚庣殑娑堟伅
- 鏌ョ湅鍙敤鍗犱綅绗?
- 鍚?live Telegram 閰嶇疆鍙戦€佹祴璇曟秷鎭?
- 鍚?sim Telegram 閰嶇疆鍙戦€佹祴璇曟秷鎭?

## 鍚姩

```powershell
cd D:\Playground\freqtrade-local
py -m streamlit run D:\Playground\freqtrade-local\apps\streamlit\telegram_template_lab.py --server.address 127.0.0.1 --server.port 8503
```

鎴栧弻鍑伙細

`D:\Playground\freqtrade-local\Launch Telegram Template Lab.cmd`

鎵撳紑锛?

[http://127.0.0.1:8503](http://127.0.0.1:8503)

## 鐩稿叧鏂囦欢

- 闈㈡澘锛歚D:\Playground\freqtrade-local\apps\streamlit\telegram_template_lab.py`
- 妯℃澘锛歚D:\Playground\freqtrade-local\telegram_message_template.json`
- live Telegram 閰嶇疆锛歚D:\Playground\freqtrade-local\openclaw.notification.json`
- sim Telegram 閰嶇疆锛歚D:\Playground\freqtrade-local\openclaw.notification.sim.json`

## 妯℃澘鍗犱綅绗?

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

