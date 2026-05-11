# AlternativeHunter 璋冨弬璇存槑

## 鐢ㄩ€?

杩欎釜鏂囦欢璇存槑 `AlternativeHunter` 鍦ㄧ瓥鐣ヨ皟璇曢潰鏉块噷鐨勫彲璋冨弬鏁般€?

鐩稿叧鏂囦欢锛?

- 绛栫暐锛?
  - `D:\Playground\freqtrade-local\user_data\strategies\AlternativeHunter.py`
- 璋冭瘯闈㈡澘锛?
  - `D:\Playground\freqtrade-local\apps\streamlit\strategy_debug_lab.py`
- 杩愯鏃剁瓥鐣ワ細
  - `D:\Playground\freqtrade-local\user_data\model_runtime_policy.json`
- 璋冭瘯涓存椂绛栫暐锛?
  - `D:\Playground\freqtrade-local\user_data\model_runtime_policy.debug.json`

## 鍩虹瀛楁

杩欎簺瀛楁鏉ヨ嚜 OpenClaw 鐨?stable 妯″瀷杈撳嚭锛屼笉鏄墜宸ヨ緭鍏ャ€?

### `decision`

- `tradable`锛氬厑璁镐氦鏄?
- `observe`锛氳瀵?
- `pause`锛氭殏鍋?

### `direction_bias`

- `long`锛氬亸鍋氬
- `short`锛氬亸鍋氱┖
- `both`锛氬弻鍚戦兘鍙?

### `model_score`

鍏ㄦ牱鏈ā鍨嬬患鍚堝垎銆傝秺楂橀€氬父璇存槑璇ュ竵鏁翠綋璐ㄩ噺瓒婇珮銆?

### `recent_model_score`

杩戞湡妯″瀷鍒嗐€傝秺楂樿鏄庢渶杩戣繖娈垫椂闂存洿鍊煎緱閲嶈銆?

### `stake_scale`

甯佺鍩虹浠撲綅鍊嶇巼銆?

甯歌鍚箟锛?

- `1.0`锛氭甯?
- `0.75`锛氱缉浠?
- `0.5`锛氬崐浠?
- `0`锛氬熀鏈鐢?

### `leverage_cap`

璇ュ竵鍏佽鐨勬渶澶ф潬鏉嗕笂闄愩€?

### `bias_strength`

鏂瑰悜鍋忕疆寮哄害銆傝秺楂樿鏄庢ā鍨嬪鍋氬鎴栧仛绌虹殑鍋忓ソ瓒婃槑纭€?

### `recent_weight`

杩戞湡鍥犲瓙鏉冮噸銆傝秺楂樿鏄庢渶杩戣〃鐜板簲褰撹鏇村己鍦扮撼鍏ュ喅绛栥€?

## 鍙皟鍙傛暟

杩欎簺鍙傛暟鍦ㄨ皟璇曢潰鏉块噷淇敼锛屽彧褰卞搷璋冭瘯鍥炴祴锛屼笉褰卞搷 live bot銆?

### `stake_weight`

鎺у埗妯″瀷鍋忕疆瀵逛粨浣嶅ぇ灏忕殑褰卞搷寮哄害銆?

- `0`锛氫笉鏍规嵁妯″瀷璋冩暣浠撲綅
- `1`锛氭寜褰撳墠榛樿閫昏緫璋冩暣
- `>1`锛氶珮缃俊甯佹洿閲嶏紝浣庣疆淇″竵鏇磋交

寤鸿鑼冨洿锛?

- 绋冲仴锛歚0.6 - 1.0`
- 婵€杩涳細`1.1 - 1.5`

### `leverage_weight`

鎺у埗妯″瀷鍋忕疆瀵规潬鏉嗗ぇ灏忕殑褰卞搷寮哄害銆?

- `0`锛氫笉鏍规嵁妯″瀷璋冩暣鏉犳潌
- `1`锛氶粯璁ゅ己搴?
- `>1`锛氶珮缃俊鏂瑰悜鏉犳潌鏇撮珮锛屼綆缃俊鏂瑰悜鏇翠綆

寤鸿鑼冨洿锛?

- 绋冲仴锛歚0.5 - 1.0`
- 婵€杩涳細`1.0 - 1.4`

### `same_side_recent_boost`

褰撴ā鍨嬫柟鍚戝拰寮€浠撴柟鍚戜竴鑷存椂锛宍recent_weight` 甯︽潵鐨勬斁澶х郴鏁般€?

鍊艰秺澶э紝杩戞湡琛ㄧ幇寮虹殑甯佹斁澶ц秺鏄庢樉銆?

寤鸿鑼冨洿锛?

- `0.3 - 0.7`

### `same_side_bias_multiplier`

褰撴ā鍨嬫柟鍚戝拰寮€浠撴柟鍚戜竴鑷存椂锛宍bias_strength` 鐨勬斁澶у€嶇巼銆?

鍊艰秺澶э紝鏂瑰悜鏄庣‘鐨勫竵浼氳鏇村己鏀惧ぇ銆?

寤鸿鑼冨洿锛?

- `2.0 - 5.0`

### `opposite_side_penalty`

褰撳紑浠撴柟鍚戝拰妯″瀷鍋忕疆鐩稿弽鏃讹紝鐩存帴鎵ｅ噺鐨勬儵缃氬€笺€?

鍊艰秺澶э紝閫嗙潃妯″瀷鏂瑰悜寮€浠撹秺闅俱€?

寤鸿鑼冨洿锛?

- `0.3 - 0.6`

### `opposite_side_recent_penalty`

褰撳紑浠撴柟鍚戜笌妯″瀷鍋忕疆鐩稿弽鏃讹紝杩戞湡鏉冮噸棰濆甯︽潵鐨勬儵缃氥€?

鍊艰秺澶э紝閫嗙潃杩戞湡鏂瑰悜寮€浠撹秺闅俱€?

寤鸿鑼冨洿锛?

- `0.1 - 0.3`

### `bias_block_threshold`

褰?`bias_strength` 杈惧埌杩欎釜闃堝€兼椂锛屽厑璁哥洿鎺ュ皝鎺夊弽鏂瑰悜寮€浠撱€?

鍊艰秺浣庯紝瓒婂鏄撳皝杈广€?

寤鸿鑼冨洿锛?

- `0.010 - 0.020`

### `recent_weight_block_threshold`

褰?`recent_weight` 杈惧埌杩欎釜闃堝€兼椂锛屽厑璁镐粎鏍规嵁杩戞湡淇″彿灏佹帀鍙嶆柟鍚戙€?

鍊艰秺浣庯紝杩戞湡璧板娍鐨勪紭鍏堢骇瓒婇珮銆?

寤鸿鑼冨洿锛?

- `0.35 - 0.55`

### `minimum_side_multiplier`

鍗曡竟鏈€灏忎繚搴曞€嶇巼銆?

鍗充娇琚儵缃氾紝涔熶笉浼氫綆浜庤繖涓€笺€?

寤鸿鑼冨洿锛?

- `0.05 - 0.15`

## 鍙傛暟浣滅敤浣嶇疆

### 寮€浠撹繃婊?

鍑芥暟锛?

- `confirm_trade_entry()`

涓昏鍙楄繖浜涘弬鏁板奖鍝嶏細

- `bias_block_threshold`
- `recent_weight_block_threshold`
- `direction_bias`
- `bias_strength`
- `recent_weight`

### 浠撲綅澶у皬

鍑芥暟锛?

- `custom_stake_amount()`

涓昏鍙楄繖浜涘弬鏁板奖鍝嶏細

- `stake_weight`
- `stake_scale`
- `same_side_recent_boost`
- `same_side_bias_multiplier`
- `opposite_side_penalty`

### 鏉犳潌澶у皬

鍑芥暟锛?

- `leverage()`

涓昏鍙楄繖浜涘弬鏁板奖鍝嶏細

- `leverage_weight`
- `leverage_cap`
- 鏂瑰悜鍋忕疆鐩稿叧鍙傛暟

## 鎺ㄨ崘璧锋鍙傛暟

濡傛灉瑕佸仛涓€缁勫亸绋崇殑娴嬭瘯锛屽彲浠ュ厛璇曪細

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

杩欑粍鐨勭壒鐐癸細

- 鏇村亸椤哄娍
- 鍙嶅悜鍗曟洿瀹规槗琚帇缂?
- 鏉犳潌姣旈粯璁ゆ洿淇濆畧

## 璇存槑

- 闈㈡澘閲岀殑璋冨弬鍙奖鍝嶈皟璇曞洖娴嬨€?
- live bot 涓嶈鍙栬繖浠戒复鏃惰皟璇曞弬鏁般€?
- 璋冭瘯缁撴灉浠嶇劧鍐欏叆锛?
  - `D:\Playground\freqtrade-local\user_data\backtest_results`

