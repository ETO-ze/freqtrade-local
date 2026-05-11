# Strategy Debug Lab

鏈湴绛栫暐璋冭瘯灏忛潰鏉匡紝涓撻棬缁?`AlternativeHunter` 杩欑被鈥滄ā鍨嬮┍鍔ㄨ繍琛屾椂绛栫暐鈥濈敤銆?

## 鍔熻兘

- 鏌ョ湅褰撳墠 `model_runtime_policy.json`
- 鏌ョ湅姣忎釜甯佺殑锛?
  - `decision`
  - `direction_bias`
  - `stake_scale`
  - `leverage_cap`
  - `model_score / recent_model_score`
- 鏌ョ湅褰撳墠 stable 鏈€浼樻ā鍨嬪拰 top factors
- 缁嗚皟鏉冮噸锛?
  - `stake_weight`
  - `leverage_weight`
  - `same_side_recent_boost`
  - `same_side_bias_multiplier`
  - `opposite_side_penalty`
  - `opposite_side_recent_penalty`
  - `bias_block_threshold`
  - `recent_weight_block_threshold`
  - `minimum_side_multiplier`
- 鐢熸垚涓存椂鍥炴祴閰嶇疆
- 鐢熸垚涓存椂 debug policy锛屼笉褰卞搷 live bot
- 涓€閿窇 `AlternativeHunter` 鍥炴祴
- 灞曠ず鏈€鏂板洖娴嬫憳瑕佸拰鍒嗗竵缁撴灉

## 鍚姩

```powershell
cd D:\Playground\freqtrade-local
py -m streamlit run D:\Playground\freqtrade-local\apps\streamlit\strategy_debug_lab.py --server.address 127.0.0.1 --server.port 8502
```

鎴栧弻鍑伙細

`D:\Playground\freqtrade-local\Launch Strategy Debug Lab.cmd`

鎵撳紑锛?

[http://127.0.0.1:8502](http://127.0.0.1:8502)

## 鍏抽敭鏂囦欢

- 闈㈡澘鑴氭湰锛?
  - `D:\Playground\freqtrade-local\apps\streamlit\strategy_debug_lab.py`
- 杩愯鏃剁瓥鐣ワ細
  - `D:\Playground\freqtrade-local\user_data\model_runtime_policy.json`
- 榛樿鍥炴祴閰嶇疆锛?
  - `D:\Playground\freqtrade-local\user_data\config.backtest.alternativehunter.json`
- 涓存椂鍥炴祴閰嶇疆锛?
  - `D:\Playground\freqtrade-local\user_data\config.backtest.strategylab.json`
- 涓存椂 debug policy锛?
  - `D:\Playground\freqtrade-local\user_data\model_runtime_policy.debug.json`

## 璇存槑

- 杩欎釜闈㈡澘涓嶄細鏀瑰姩 live bot 閰嶇疆銆?
- 瀹冨彧鐢熸垚鐙珛鐨勪复鏃?backtest config 鍜?debug policy銆?
- 鍥炴祴缁撴灉浠嶇劧钀藉湪锛?
  - `D:\Playground\freqtrade-local\user_data\backtest_results`

