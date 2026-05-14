# 项目框架与主流量化策略对照报告

生成时间：2026-05-13

范围：本报告只做项目梳理、连通性验证和策略建议，不修改实盘配置，不重启云端 Freqtrade，不构成投资建议。

## 1. 本地项目框架

### 核心源码

- `apps/desktop/`：OpenClaw + Freqtrade 本地总控 GUI。
- `apps/streamlit/`：因子实验室、策略调试、Telegram 模板面板。
- `scripts/windows/`：Windows 启停脚本、同步入口、GitHub 安全同步、walk-forward 入口。
- `scripts/workflows/`：动态币池、robust screen、dashboard 数据发布、服务器探测、云端同步、walk-forward 任务。
- `site/dashboard/`：Vue3 网站看板，展示回测、审批历史、实盘只读摘要和告警。
- `site/landing/`：duskrain 首页。
- `server/`：服务端状态构建和网站辅助脚本。
- `user_data/notebooks/`：训练、进化、autotune、交易反馈分析等实验脚本。
- `user_data/strategies/`：Freqtrade 策略文件，当前核心策略是 `AlternativeHunter.py`。
- `docs/`：项目说明、操作指南、架构和决策记录。

### 运行产物和缓存

- `reports/`：训练、审批、Telegram、服务器探测、daemon 状态报告。
- `dashboard-data/`：发布给网站看板的 JSON 数据。
- `user_data/backtest_cache/`：回测缓存。
- `user_data/backtest_results/`：Freqtrade 回测 zip。
- `backups/`：本地备份。

这些目录默认不应提交 GitHub，除非后续明确做脱敏样例。

## 2. 当前流通性验证

本次做的是非破坏验证，没有重启云端实盘。

已验证：

- Python 关键脚本可以编译。
- PowerShell 关键启动脚本可以通过 Parser 检查。
- Vue dashboard 可以完成 build。
- `dashboard-data/backtest.json`、stable 日报、审批历史可用 `utf-8-sig` 正常读取。
- dashboard JSON 发布已改成临时文件校验后原子替换，降低半写入风险。
- 新增 `scripts/workflows/validate_openclaw_runtime_artifacts.py`，用于检查 dashboard、报告和 daemon 状态 JSON。
- 服务器探测报告 `reports/openclaw-server-status-latest.json` 存在且可读。
- stable 链路最近能跑完 `market_data_refresh`、`dynamic_universe`、`robust_screen`、`local_model_training`、`walk_forward_retrain`、`auto_backtest`、`publish_dashboard_data`。

需要继续观察：

- `autotune` 检查时仍处于运行状态，后续要确认是否完成或是否进入 stale 状态。
- Docker 内存仍是训练失败风险点，之前出现过 `exit code 137`，这通常是容器内存不足或被系统杀掉。
- 报告文件历史上存在 BOM/编码差异，建议后续统一 JSON 写入编码，并在发布前做 JSON validation。

## 3. 当前因子状态

### Active 因子

- 策略：`AlternativeHunter`
- 模型：`HistGradientBoostingClassifier`
- 审批模式：`experimental_high_profit`
- 最近 active 回测：`backtest-result-2026-05-05_07-32-48.zip`
- 总收益：`219.68%`
- PF：`1.77`
- 胜率：`68.39%`
- 最大回撤：`24.88%`
- 交易数：`484`
- active 币种：`PENGU`、`TURBO`、`FLOKI`、`BONK`、`SAHARA`、`PEPE`、`TRIA`

结论：这是一个高收益高风险因子。收益高，但回撤接近 25%，不应被描述成稳健策略。

### 最新候选结果

- 最近候选回测收益约 `5.47%`
- PF `1.58`
- 胜率 `67.14%`
- 最大回撤 `4.30%`
- 交易数 `70`
- 结果：未触发云端同步，promotion gate 未通过。

结论：近期没有新因子替代 active 是合理的。当前保护逻辑应该保留：没有更优候选时不替换 active。

### 特征集中度问题

active 结果里主要权重集中在：

- `mark_premium_zscore_48`
- `mark_premium_abs`
- `atr_14_pct`
- `mark_premium_change_3`
- `volatility_24`
- `volatility_12`
- `eth_beta_48`
- `funding_rate_zscore_48`

风险：`mark_premium` 家族权重过高，容易把模型变成“资金费率/溢价状态识别器”，而不是更完整的趋势、动量、流动性和风险模型。

## 4. 公开研究参考

### Crypto 横截面因子

NBER/Journal of Finance 的 “Common Risk Factors in Cryptocurrency” 指出，crypto 横截面收益可以用 market、size、momentum 三类因子解释，说明“动态币池 + 横截面排名”是合理方向。

参考：[Common Risk Factors in Cryptocurrency, NBER](https://www.nber.org/papers/w25882)

### 时间序列动量

Moskowitz、Ooi、Pedersen 的 “Time Series Momentum” 是成熟的趋势跟随研究基础。它支持用单资产自身过去走势判断趋势延续，但需要结合波动状态和风险控制。

参考：[Time Series Momentum, Journal of Financial Economics PDF](https://pages.stern.nyu.edu/~lpederse/papers/TimeSeriesMomentum.pdf)

### Crypto 动量与反转

Crypto 市场里 momentum 和 reversal 都有研究证据，且效果会受到流动性、市值和周期影响。这说明山寨币不能只用一个固定窗口做动量，也不能只做反转；应该按流动性和 regime 区分。

参考：[Momentum or reversal: Which is the appropriate third factor for cryptocurrencies?](https://www.sciencedirect.com/science/article/pii/S1544612321002208)

参考：[Up or down? Short-term reversal, momentum, and liquidity effects in cryptocurrency markets](https://www.sciencedirect.com/science/article/pii/S1057521921002349)

### Perpetual funding/carry

Perpetual futures 的 funding 机制本质上是让永续价格靠近现货价格，资金费率能表达市场拥挤和杠杆方向，但也会受交易所结构和流动性影响。它更适合做风险/拥挤度判断，不适合作为唯一 alpha。

参考：[Fundamentals of Perpetual Futures](https://arxiv.org/abs/2212.06888)

参考：[The Two-Tiered Structure of Cryptocurrency Funding Rate Markets](https://www.mdpi.com/2227-7390/14/2/346)

## 5. 当前不足

### 5.1 后段 gate 与 objective 仍不完全一致

训练目标如果偏向模型分类分数，而 promotion gate 看收益、PF、回撤、胜率、交易数，就会出现“模型分数不错，但回测不达标”的情况。

建议：objective 直接加入收益、PF、回撤惩罚、交易数惩罚、单币集中度惩罚。

### 5.2 mark premium 家族过度主导

当前 active 结果对 mark premium 依赖过高。这个信号在某些行情中可能有效，但泛化风险较大。

建议：

- 设置 feature family cap。
- 对 `mark_premium_abs` 做降权或消融实验。
- funding/mark premium 从 alpha 主因子改成风险因子或拥挤度因子。

### 5.3 动态币池仍需要更强过滤

山寨币流动性变化快，动态币池是对的，但需要避免空气币、异常集中成交、过度拉盘币、数据太短币。

建议：

- core 15 + expand 40。
- 对 expand 币只做 probe/observe，不直接进入 active。
- 加成交额、上市时长、极端滑点、单日异常成交过滤。

### 5.4 回测稳定性还不够

当前 active 高收益但高回撤，且 Sharpe/Sortino/Calmar 等字段缺失或不完整。

建议 promotion 增加：

- 分段回测。
- 月度收益分布。
- 单币贡献集中度。
- 最大回撤恢复时间。
- long/short 分开统计。
- 最近 60-120 天窗口表现。

### 5.5 实盘保护还要继续明确

云端负责实盘，因此本地同步必须知道云端是否有持仓。

建议：

- 策略更新前同步持仓摘要。
- 有持仓时允许“只更新下一轮配置”或延迟重启。
- dashboard 显示当前持仓数量、方向、杠杆、浮盈、总收益。

## 6. 建议架构

### 6.1 信号层

使用“横截面排名 + 时间序列确认”：

- 横截面：同一时刻比较山寨币相对强弱、1d/3d/7d 动量、成交量增长、相对 BTC/ETH 表现。
- 时间序列：单币 EMA、ADX、ATR、突破、回撤恢复、波动收缩后放量。
- 风险因子：funding、mark premium、极端波动、流动性骤降。

### 6.2 Regime 层

BTC/ETH 市场状态控制器：

- BTC/ETH 向上：允许山寨多头，提高仓位。
- BTC/ETH 震荡：只交易排名最高、波动适中的币。
- BTC/ETH 下跌或高波动：降低仓位、减少开仓，只允许 short 或空仓。

### 6.3 仓位和杠杆层

不建议固定大胆加杠杆，建议使用波动率目标：

```text
target_leverage = base_leverage * score_factor * regime_factor * volatility_factor * drawdown_guard
```

先在回测中限制：

- 常规通道：1x-3x。
- 实验通道：4x-5x，但必须展示回撤和爆仓风险。
- 高波动币即使高分也不直接满杠杆。

### 6.4 Promotion 层

候选因子不只比较总收益，还要比较稳定性：

- 总收益。
- PF。
- 胜率。
- 最大回撤。
- 交易数。
- 月度收益稳定性。
- 单币贡献集中度。
- long/short 失衡程度。
- 最近窗口是否仍有效。

## 7. 优先级建议

第一优先级：运行稳定性。

- JSON 写入统一编码，并已对 dashboard 发布链路加入原子写入。
- 发布前做 JSON validation，已新增本地运行产物验证脚本。
- daemon status 防 stale。
- Docker 内存保护和并发限制。
- 回测缓存复用。

第二优先级：模型稳健性。

- objective 贴近 promotion gate。
- feature family cap。
- mark premium 消融。
- walk-forward 从 report-only 积累样本。

第三优先级：策略收益结构。

- BTC/ETH regime 控制器。
- 横截面 ranking + 时间序列确认。
- funding/mark premium 风险化。
- 波动率目标仓位和杠杆。

第四优先级：实盘安全。

- 云端持仓定时同步。
- 有持仓时策略切换保护。
- active 与 candidate 对比展示。
- 手动同步入口保留，自动同步只走审批结果。

## 8. 推荐下一步执行

1. 先修运行稳定性：JSON 原子写入、编码统一、daemon stale 检测、Docker 内存提示。
2. 再做模型结构：feature family cap + mark premium 消融 + objective 对齐 promotion gate。
3. 再做策略结构：BTC/ETH regime + 横截面 ranking + 时间序列确认。
4. 最后再把 walk-forward 从 report-only 升级为半强制 gate。

当前不建议直接追求更高杠杆。更合理的顺序是先让信号更稳、仓位更自适应，再用实验通道测试 4x-5x。
