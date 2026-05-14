# OpenClaw + Freqtrade Documentation

## 当前状态

- 项目根目录：`D:\Playground\freqtrade-local`。
- 当前日期：2026-05-13。
- 当前主策略：`AlternativeHunter`。
- 当前执行分工：本地训练、筛选、回测、promotion；云端 Freqtrade 负责实盘执行。
- 当前 active 因子：`HistGradientBoostingClassifier`，`experimental_high_profit` 通道，回测收益约 `219.68%`，PF `1.77`，胜率 `68.39%`，最大回撤 `24.88%`，交易数 `484`。
- 当前 active 币种：`PENGU`、`TURBO`、`FLOKI`、`BONK`、`SAHARA`、`PEPE`、`TRIA`。
- 最新 stable 候选：`2026-05-13 16:18` 这一轮已完整跑通，收益约 `143.03%`，PF `1.28`，胜率 `67.93%`，最大回撤 `50.89%`，交易数 `842`。因为 PF、回撤、稳定性和 walk-forward 不达标，未触发云端同步。
- 当前特征风险：active 结果中 `mark_premium_zscore_48` 和 `mark_premium_abs` 权重过高，存在单一特征家族主导风险。

## 本地文件框架

- `apps/desktop/`：本地总控 GUI，负责启动/停止、状态展示、云端同步入口、GitHub 同步入口。
- `apps/streamlit/`：因子实验室、策略调试、Telegram 模板面板。
- `scripts/windows/`：Windows 启停脚本、同步脚本、walk-forward 入口、GitHub 安全同步脚本。
- `scripts/workflows/`：动态币池、robust screen、dashboard 发布、服务器探测、云端同步、walk-forward 等自动化脚本。
- `site/dashboard/`：Vue3 网站看板。
- `site/landing/`：duskrain 首页。
- `server/`：服务端状态构建和辅助脚本。
- `user_data/notebooks/`：训练、进化、autotune、交易反馈分析等研究脚本。
- `user_data/strategies/`：Freqtrade 策略文件。
- `docs/`：说明、操作指南、结构梳理和设计文档。
- `reports/`：运行报告，不提交。
- `dashboard-data/`：网站数据发布中间产物，不提交。
- `user_data/backtest_cache/`：回测缓存，不提交。
- `user_data/backtest_results/`：Freqtrade 回测 zip，不提交。
- `backups/`：本地备份，不提交。

## 决策记录

- 本地和云端分离：本地可以失败、重训、筛选，云端只接收已审批 active 配置。
- 未达标候选不得覆盖 active 因子。
- 高收益高风险通道可以保留，但必须明确展示回撤、PF、胜率和交易数。
- `walk-forward` 先作为 report-only 观察，不直接阻断 promotion。
- `mark premium` 和 `funding` 不应长期单独主导开仓，后续应作为风险/拥挤度因子限制权重。
- 动态币池要继续保留，因为山寨币流动性变化快；但需要增加集中度、空气币和低流动性过滤。
- 云端实盘有持仓时，策略更新必须有保护：先同步只读持仓，再决定是否延迟切换或只更新下一轮配置。

## 本次流通性检查结果

- Python 编译：关键脚本通过。
- PowerShell Parser：关键 `.ps1` 脚本通过。
- Vue dashboard build：通过；存在一条静态背景资源运行时解析 warning，不影响 build。
- JSON 读取：`dashboard-data/backtest.json`、stable 报告、审批历史可用 `utf-8-sig` 正常读取。
- JSON 发布：`publish_dashboard_public_data.py` 和 `server/build_dashboard_status.py` 已改为临时文件校验后原子替换，降低半写入导致看板白屏或数据断裂的风险。
- 服务器探测：`probe_openclaw_server_status.py` 已改为 JSON/Markdown 原子写入。
- 运行产物验证：`scripts/workflows/validate_openclaw_runtime_artifacts.py` 已增强，可检查 dashboard、报告、daemon 状态、active 因子、latest candidate、mark premium 特征集中度和 stale 风险，并输出 `reports/openclaw-runtime-validation-latest.json/.md`。
- 市场数据刷新：`refresh_alt_market_data.ps1` 已增加重试和缓存降级。OKX 短时网络失败时，如果本地 5m futures 缓存覆盖率达标且足够新，stable 流程会继续使用缓存，不再直接中断。
- 报告写入：动态币池、walk-forward、stability、trade feedback、evolution、autotune 的关键 JSON/Markdown 已逐步改为临时文件替换写入，降低 GUI/网站读取半文件的概率。
- daemon 状态写入：fast、stable、evolution、autotune 启动脚本和通用停止脚本已改为 pid/status/stop 临时文件替换写入，降低 GUI 读取 stale 或半写入状态的概率。
- daemon 启动判定：启动器已修复“status=ok 但 daemon 仍在睡眠等待下一轮时被误判为 stale 并重启”的问题。现在只要匹配 daemon 进程仍然存在，默认不会重复启动；需要重启时使用 `-ForceRestart`。
- stable 流程：`2026-05-13 16:18` 重跑成功；market refresh、dynamic universe、robust screen retry、model training、walk-forward、candidate backtest、trade feedback 全部跑到结束。
- stable 审批：候选收益 `143.03%`，但 PF `1.28`、最大回撤 `50.89%`、stability score `0.0`、walk-forward `0/3`，因此按保护规则拒绝，未更新云端实盘。
- Docker：有 Freqtrade 相关容器运行；训练内存仍需注意。
- 服务器探测：`reports/openclaw-server-status-latest.json` 已生成并可读。
- daemon 状态：`stable` 和 `autotune` 在检查时处于运行中，`fast` 处于 waiting；后续需以最新 status JSON 为准。

## 完成日志

- `2026-05-13`：完成原子写入专项并从 `Plan.md` 移除。覆盖范围包括 dashboard 发布、服务端 status、服务器探测、训练报告、动态币池、walk-forward、stability、trade feedback、evolution、autotune、本地云端同步、Windows daemon pid/status/stop 文件，以及外部 OpenClaw 工作流 `D:\Playground\openclaw\scripts\freqtrade-daily-ml-screen.ps1` 的关键 JSON/Markdown 输出和 latest alias 拷贝。
- `2026-05-13`：修复 daemon 启动判定。只要匹配 daemon 进程仍存在，`ok/waiting/error` 状态不再被误判为 stale 并强制重启；需要重启时显式使用 `-ForceRestart`。
- `2026-05-13`：确认 stable 至少完整跑通一轮，候选被拒绝是策略质量和稳定性不达标，不是流程中断。
- `2026-05-13`：完成 feature family cap 子项并从 `Plan.md` 移除。训练报告新增 `capped_top_features`、`capped_feature_family_shares`、`feature_family_excess_share`；OpenClaw 聚合高优先级因子时优先使用 capped top features，减少 `mark_premium`/`funding` 等单一家族对策略建议的主导。
- `2026-05-13`：启动 mark premium 消融实验能力。`train_alt_tree_models.py` 新增 `--exclude-feature-families mark_premium`，可生成去除 mark premium 家族的模型训练对照；下一步需要接入候选回测对比收益、PF、回撤和交易数。
- `2026-05-13`：完成 OpenClaw stable 的可选 feature family ablation report-only 链路。`D:\Playground\openclaw\scripts\freqtrade-daily-ml-screen.ps1` 新增 `FeatureFamilyAblationEnabled`，开启后会额外训练排除指定特征族的对照模型，输出 `reports/openclaw-feature-family-ablation-latest.json/.md`，并写入 combined report/JSON；默认关闭，不影响常规 stable 运行。
- `2026-05-13`：完成运行产物验证 milestone 并从 `Plan.md` 移除。验证命令已确认 dashboard、stable report、auto-backtest、approved history、server status 和 daemon status 均可读；当前仅保留 warning/info，包括 active 因子 `mark_premium` 主导、latest candidate 弱于 active、evolution 状态文件缺失。
- `2026-05-13`：完成动态币池分层的 report/data 侧接入。`build_dynamic_alt_universe.py` 新增 `core/expand/observe/pause` 分层输出，ranking 行新增 `pool` 字段；OpenClaw stable 新增 `DynamicUniverseCoreN/ExpandN/RankingN/ObserveMinScore` 参数并传递给动态币池脚本。验证方式使用临时输出跑通，不覆盖正式配置。
- `2026-05-13`：完成 promotion gate 机器可读审批摘要。OpenClaw stable 新增 `ApprovalJsonPath`，输出 `openclaw-auto-approval-latest.json`，包含 standard/experimental gate 逐项 pass/fail、stability、walk-forward、promotion protection、最终 `approved_for_sync` 和 result zip，用于后续 GUI/网站展示拒绝原因。
- `2026-05-13`：完成网站回测页 gate breakdown 接入。`publish_dashboard_public_data.py` 将 approval JSON 合并进 `dashboard-data/backtest.json`，Vue 回测结果页在最新候选卡片展示 standard/experimental gate 的逐项 PASS/FAIL；`npm run build` 已通过。
- `2026-05-13`：完成候选配置的动态池过滤。`freqtrade-sync-screen-to-config.ps1` 新增 `AllowedDynamicPools`，OpenClaw stable 默认传入 `CandidateAllowedDynamicPools=core`，只让 core 池进入候选回测/同步；若过滤后无候选，会回退到原始候选，避免 stable 链路因池分层过严中断。
- `2026-05-13`：运行产物校验补充 approval/dynamic universe 检查。`validate_openclaw_runtime_artifacts.py` 现在会读取 approval JSON、动态币池 pool counts、审批 failed gate checks；`openclaw-auto-approval-latest.json` 是新增产物，下一轮 stable 生成前缺失不作为阻断。
- `2026-05-13`：完成 expand/probe backtest-only 对照链路。OpenClaw stable 新增 `ProbeBacktestEnabled`、`ProbeBacktestAllowedDynamicPools`、`ProbeCandidateConfigPath`、`ProbeBacktestReportPath/JsonPath`。默认关闭；开启后只对 expand/observe 池生成独立 probe 配置并回测，结果写入 approval/combined/dashboard，但永不参与 automatic promotion。
- `2026-05-13`：补强 BTC/ETH regime 与杠杆风险透明度。runtime policy 已持续写入 regime/risk/leverage/volatility/trend scale；高于 3x 的币种现在会标记 `experimental_high_risk`，并在策略更新报告里列出，避免实验高杠杆被误认为稳健通道。
- `2026-05-13`：增强 walk-forward report-only 稳定性摘要。`run_walk_forward_retrain.py` 新增 `stability_summary`，输出窗口通过率、失败窗口、Docker 137 内存失败、模型共识、特征家族集中度、正交因子占比和 `recommended_gate_mode`；Markdown 报告新增 `Stability Summary`。当前仍不作为硬 gate，只用于后续观察和半强制 gate 设计。
- `2026-05-13`：网站回测结果页接入 walk-forward 稳定性摘要。`backtest-data.ts` 新增 `stability_summary` 类型，`BacktestResultsView.vue` 展示稳定等级、建议 gate 模式、模型共识率、特征家族集中度、正交因子占比、内存失败次数和阻断原因；`npm run build` 已通过。
- `2026-05-13`：云端只读持仓探测补齐。`probe_openclaw_server_status.py` 读取 Freqtrade `/status`，生成 `open_trade_check`，包含持仓数量、币种、方向、杠杆、浮盈、开仓时间和总浮盈；`publish_dashboard_public_data.py` 已把该字段发布到 `dashboard-data/backtest.json`，网站实盘只读摘要已展示。当前探测结果：云端 API 正常，持仓数量为 `0`。
- `2026-05-13`：网站接入特征家族消融只读展示。`publish_dashboard_public_data.py` 发布 `feature_family_ablation`，`BacktestResultsView.vue` 展示消融状态、排除家族、主模型/消融模型、权重差和风险说明；当前未生成正式消融 JSON 时会回退到 stable daily report 中的字段或空数据，不影响页面构建。
- `2026-05-13`：补强 Git 忽略规则。`.gitignore` 新增 `dashboard-data/`、`backups/`、`user_data/backtest_cache/`、`user_data/model_runtime_policy.debug.json` 和 `user_data/config.openclaw-auto.before-*.json`，避免运行缓存、备份和本地调试配置被误提交。

## 公开研究参考结论

- Crypto 动量/反转因子有研究支持，但需要分市场阶段和窗口，不能只依赖单一短周期信号。
- 时间序列趋势跟随是成熟量化思路，适合加入 BTC/ETH regime 判断。
- 横截面 ranking 适合山寨币轮动，但必须配合流动性、成交额、波动率和集中度过滤。
- Funding/carry 更适合作为风险和拥挤度因子，不建议长期作为唯一 alpha。
- 波动率目标和分段验证比固定高杠杆更稳健。

参考文档见：`docs/project/PROJECT_FRAMEWORK_AND_QUANT_REVIEW.md`。

## 下一步优先级

1. 数据和运行稳定性：统一 JSON 编码为 UTF-8 无 BOM 或读取端统一 `utf-8-sig`；发布前做 JSON validation；重要文件原子写入。
2. 训练效率：控制 Docker 内存、限制并发容器、复用 `user_data/backtest_cache/`，长历史数据先缓存后训练。
3. 模型稳健性：加入 feature family cap，降低 mark premium 家族单独主导风险；做 mark premium 消融对照。
4. 策略结构：从“单模型选币”升级为“横截面排名 + 时间序列确认 + BTC/ETH regime + 波动率目标仓位”。
5. 风控和审批：promotion gate 增加多窗口稳定性、单币贡献集中度、月度收益分布、回撤恢复时间。
6. 看板补齐：展示 active 与 latest candidate 对比、已审批因子、walk-forward、实盘持仓总收益和多空方向。

## 当前优化清单

- 运行产物诊断：已开始，验证脚本已增强。
- JSON 原子写入：专项已完成，详见“完成日志”。后续只在新增报告脚本时按同一规则实现。
- 云端同步写入：`sync_openclaw_runtime_to_server.py` 已将本地同步报告和远端 `last-sync.json` 改成原子写入。
- 市场数据刷新：已完成重试和缓存降级，解决 OKX 临时连接失败导致 stable 直接 error 的问题。
- 训练报告：`train_alt_tree_models.py` 已加入 JSON/Markdown 原子写入，并在模型报告中标记 `feature_family_risk`。
- 特征集中度：已开始可视化风险标记；`D:\Playground\openclaw\scripts\freqtrade-daily-ml-screen.ps1` 已加强模型选择权重惩罚，mark premium 超 40%、最大特征族超 55%、`feature_family_risk=high` 会进一步降权。feature family cap 已完成，mark premium 消融训练入口和 stable report-only 对照链路已完成，候选回测对比仍待做。
- objective 对齐：审批链路已输出机器可读 gate breakdown；下一步把收益、PF、回撤、交易数、稳定性纳入训练筛选目标，并把 breakdown 接入 GUI/网站。
- 动态币池：数据和报告层已拆分 core / expand / observe / pause；候选配置已默认限制 core；expand/probe 已支持 backtest-only 对照，不直接进入 promotion。下一步观察多轮 probe 结果，再决定是否允许半自动候选。
- BTC/ETH regime：基础风险透明度已补强，后续重点是观察高风险通道回测/实盘只读持仓，再决定是否增加显式手动开关。
- Walk-forward：已补充稳定性摘要，后续需要把候选回测收益/PF/回撤/交易数按窗口写入，用于从 report-only 升级到半强制稳定性评分。
- 实盘保护：待进一步固化有持仓时延迟重启或只更新下一轮配置。

## 常用运行命令

启动 GUI：

```powershell
cmd /c "D:\Playground\freqtrade-local\launchers\OpenClaw Control Center GUI.cmd"
```

启动 fast：

```powershell
powershell -ExecutionPolicy Bypass -File D:\Playground\freqtrade-local\scripts\windows\start-openclaw-factor-daemon-fast.ps1
```

启动 stable：

```powershell
powershell -ExecutionPolicy Bypass -File D:\Playground\freqtrade-local\scripts\windows\start-openclaw-factor-daemon-stable.ps1
```

启动因子实验室：

```powershell
powershell -ExecutionPolicy Bypass -File D:\Playground\freqtrade-local\scripts\windows\start-factor-lab.ps1
```

运行 walk-forward：

```powershell
powershell -ExecutionPolicy Bypass -File D:\Playground\freqtrade-local\scripts\windows\run-walk-forward-retrain.ps1
```

发布 dashboard 数据：

```powershell
python D:\Playground\freqtrade-local\scripts\workflows\publish_dashboard_public_data.py
```

检查运行产物：

```powershell
python D:\Playground\freqtrade-local\scripts\workflows\validate_openclaw_runtime_artifacts.py --required dashboard-data/backtest.json --required dashboard-data/alerts.json
```

构建网站看板：

```powershell
cd D:\Playground\freqtrade-local\site\dashboard
cmd /c npm run build
```

安全同步 GitHub：

```powershell
powershell -ExecutionPolicy Bypass -File D:\Playground\freqtrade-local\scripts\windows\sync-github-safe.ps1
```

## 已知问题

- Docker Desktop 内存上限可能导致模型训练 `exit code 137`。
- `autotune` 仍需要继续观察，避免“状态显示运行但实际无有效任务”的情况。
- 部分报告历史上出现过 BOM/编码差异，建议统一写入编码并在读取端兼容 `utf-8-sig`。
- `walk-forward` 当前为 report-only，不应被误认为已经启用强制稳定性门槛。
- 山寨币市场轮动快，固定币池会过时，动态币池必须保留。

## Git 注意事项

提交前必须检查：

```powershell
git status --short
git diff --stat
```

不要提交：

- `server.openclaw-sync.local.json`
- 交易所 API 或 Telegram token
- `reports/`
- `dashboard-data/`
- `user_data/backtest_cache/`
- `user_data/backtest_results/`
- 行情数据
- daemon logs
- Docker/SQLite 本地状态文件
