# OpenClaw + Freqtrade 优化计划

本计划基于当前程序状态、运行产物、网络策略调研和最近 stable/autotune 结果整理。原则：先做不影响实盘的稳定性优化，再做模型和策略结构优化，最后再扩大自动 promotion 权限。

## 当前可优化项清单

1. 运行产物可诊断性不足：之前只能确认 JSON 能否读取，不能快速判断 active 因子、候选因子、daemon stale、特征集中度和运行风险。
2. JSON 写入一致性仍需扩大：dashboard 发布和服务端 status 已原子写入，但训练、回测、进化、autotune、反馈脚本里仍有直接 `write_text`。
3. 模型特征集中度偏高：active 因子里 `mark_premium_zscore_48` 和 `mark_premium_abs` 权重过高，需要 feature family cap 和消融对照。
4. promotion objective 和实际 gate 仍需对齐：模型训练分数与最终收益、PF、回撤、胜率、交易数、稳定性指标不完全一致。
5. walk-forward 仍是 report-only：目前适合观察，但后续应逐步变成半强制稳定性评分。
6. 动态币池需要分层：`core` 用于 active，`expand/probe` 用于观察和回测，不应把高风险扩展币直接放入实盘。
7. BTC/ETH regime 控制器还不够强：山寨币仓位和杠杆应受 BTC/ETH 趋势、波动和资金费率环境约束。
8. 仓位和杠杆需要波动率目标化：高分币可以提高杠杆，但应被波动率、回撤、流动性和 regime 限制。
9. 实盘策略切换保护需要继续固化：云端有持仓时应延迟重启或只更新下一轮配置。
10. GUI 和网站看板还可以增强：显示 active vs candidate 对比、运行产物校验结果、特征集中度风险、daemon stale 风险。

## Milestone 1: 模型稳健性优化

目标：减少单一特征族主导，降低过拟合和行情失效风险。

Acceptance Criteria:

- 给特征分组：mark premium、funding、volatility、trend、momentum、liquidity、BTC/ETH relative、structure。
- 已开始：训练报告写入 `feature_family_risk`，用于提示单一特征族主导风险。
- 已开始：OpenClaw 模型选择权重已加强单一特征族惩罚，mark premium 超 40%、最大特征族超 55%、`feature_family_risk=high` 会进一步降权。
- 已完成：OpenClaw best-model JSON/Markdown 写入 `feature_family_risk`，便于 GUI/网站后续展示特征家族风险。
- 已完成：训练脚本支持 `--exclude-feature-families mark_premium`，可生成去除 mark premium 家族的模型对照。
- 已完成：OpenClaw stable 工作流支持可选 `FeatureFamilyAblationEnabled` report-only 消融，输出 `openclaw-feature-family-ablation-latest.json/.md`，默认关闭，不影响常规 stable 耗时。
- 已完成：网站回测结果页已接入 `feature_family_ablation` 只读展示，能显示消融状态、排除家族、主模型/消融模型、权重差和风险说明。
- 下一步：把消融结果接入候选回测对比，比较收益、PF、回撤和交易数，再决定是否进入 promotion objective。

Validation Commands:

```powershell
python -m py_compile D:\Playground\freqtrade-local\user_data\notebooks\train_alt_tree_models.py
Select-String -Path D:\Playground\freqtrade-local\reports\openclaw-runtime-validation-latest.md -Pattern "Mark premium"
$path='D:\Playground\openclaw\scripts\freqtrade-daily-ml-screen.ps1'; $tokens=$null; $errors=$null; [System.Management.Automation.Language.Parser]::ParseFile($path,[ref]$tokens,[ref]$errors) | Out-Null; if ($errors.Count) { $errors | Format-List *; exit 1 }
```

## Milestone 2: Objective 与 Promotion Gate 对齐

目标：让训练筛选目标更接近真实审批标准，而不是只追求模型分类分数。

Acceptance Criteria:

- objective 中加入收益不足惩罚、PF 惩罚、回撤惩罚、交易数下限惩罚。
- 高收益高风险通道单独评分，不与稳健通道混用。
- active 替换逻辑继续保护：候选未明显优于 active 时不替换。
- candidate 与 active 的收益差、胜率、回撤、PF 对比写入审批报告。
- 已完成：审批链路新增机器可读 `openclaw-auto-approval-latest.json`，包含 standard/experimental gate 的逐项 pass/fail、stability、walk-forward、promotion protection 和最终 `approved_for_sync`。
- 下一步：把 gate breakdown 接入 GUI/网站，并继续把训练 objective 与最终 gate 分数靠齐。

Validation Commands:

```powershell
Get-Content D:\Playground\freqtrade-local\reports\openclaw-auto-approval-stable.md
Get-Content D:\Playground\freqtrade-local\dashboard-data\backtest.json
Test-Path D:\Playground\freqtrade-local\reports\openclaw-auto-approval-latest.json
```

## Milestone 3: 动态币池分层

目标：山寨币池保持灵活，但不要让低确定性扩展币直接影响实盘。

Acceptance Criteria:

- `core`：通过 robust screen 且流动性稳定，用于 active/promotion。
- `expand`：市值/成交额靠前但模型确认不足，用于 probe 回测。
- `observe`：有信号但稳定性不足，只进入观察。
- `pause`：低流动性、过度异常、空气币风险或回测恶化。
- 已完成：动态币池生成器输出 `pools.core/expand/observe/pause`、ranking `pool` 字段和 Markdown 分层；OpenClaw stable 参数已接入 `DynamicUniverseCoreN/ExpandN/RankingN/ObserveMinScore`。
- 已完成：候选配置构建支持 `AllowedDynamicPools`，OpenClaw stable 默认 `CandidateAllowedDynamicPools=core`，只让 core 池进入候选回测/同步；若 core 过滤后无候选，会安全回退到原始候选，避免断流。
- 已完成：为 expand/probe 增加可选独立 backtest-only 对照。`ProbeBacktestEnabled` 默认关闭，开启后使用 `ProbeBacktestAllowedDynamicPools=expand,observe` 生成独立 probe 配置并跑回测，结果写入报告和 dashboard，但永不进入 automatic promotion。
- 下一步：观察 2-3 轮 probe backtest 后，再决定 expand 是否允许进入半自动候选。

Validation Commands:

```powershell
Get-Content D:\Playground\freqtrade-local\reports\openclaw-daily-alt-ml-stable.json
Select-String -Path D:\Playground\freqtrade-local\reports\openclaw-daily-alt-ml-stable.md -Pattern "Tradable","Observe","Pause"
$path='D:\Playground\openclaw\scripts\freqtrade-sync-screen-to-config.ps1'; $tokens=$null; $errors=$null; [System.Management.Automation.Language.Parser]::ParseFile($path,[ref]$tokens,[ref]$errors) | Out-Null; if ($errors.Count) { $errors | Format-List *; exit 1 }
```

## Milestone 4: BTC/ETH Regime 与仓位杠杆控制

目标：让山寨策略收益增强不只依赖固定杠杆，而是受市场环境控制。

Acceptance Criteria:

- BTC/ETH 向上：允许山寨多头，提高仓位。
- BTC/ETH 震荡：只交易排名最高、波动适中的币。
- BTC/ETH 下跌或高波动：降低仓位、减少开仓，必要时只允许 short 或空仓。
- 杠杆公式使用 `score_factor * regime_factor * volatility_factor * drawdown_guard`。
- 常规通道 1x-3x，实验通道 4x-5x 必须展示回撤和风险。
- 已完成：runtime policy 已写入 BTC/ETH `benchmark_regime`、`benchmark_risk_scale`、`benchmark_leverage_scale`、`volatility_scale`、`trend_scale`、方向允许和每币 `leverage_cap/stake_scale`。
- 已完成：高于 3x 的币种会标记为 `experimental_high_risk` 并写入策略更新报告，避免把实验杠杆误认为稳健通道。
- 下一步：观察高风险通道回测和实盘只读持仓，再决定是否把 4x-5x 做成显式手动开关。

Validation Commands:

```powershell
python -m py_compile D:\Playground\freqtrade-local\user_data\strategies\AlternativeHunter.py
```

## Milestone 5: Walk-forward 升级

目标：从 report-only 逐步升级为稳定性评分，最后再考虑硬 gate。

Acceptance Criteria:

- 继续记录多窗口收益、PF、回撤、交易数。
- 已完成：`run_walk_forward_retrain.py` 新增 `stability_summary`，记录窗口通过率、失败窗口、Docker 137 内存失败、模型共识、主导特征家族集中度、正交因子占比、权重均值/最小值/波动，并输出 `recommended_gate_mode`。
- 已完成：Walk-forward Markdown 报告新增 `Stability Summary`，可直接判断当前是训练失败、窗口不一致、模型共识不足，还是特征族过度集中导致不过。
- 增加窗口一致性评分。基础字段已完成，后续可接入收益/PF/回撤层面的窗口一致性。
- 增加单月爆发依赖和单币贡献集中度检测。
- 至少观察 2-3 轮 stable 后，再决定是否进入半强制 gate。

Validation Commands:

```powershell
powershell -ExecutionPolicy Bypass -File D:\Playground\freqtrade-local\scripts\windows\run-walk-forward-retrain.ps1
Get-Content D:\Playground\freqtrade-local\reports\openclaw-walk-forward-retrain-stable.json
```

## Milestone 6: GUI 和网站看板增强

目标：让状态和风险直接可见，不需要翻多个报告。

Acceptance Criteria:

- GUI 增加“运行产物校验”入口或状态摘要。
- 网站看板展示 active vs latest candidate 对比。
- 网站看板展示 mark premium 特征族权重风险。
- 网站看板展示 daemon stale / error / warning。
- 实盘只读摘要继续显示持仓数量、方向、杠杆、浮盈、总收益。
- 已完成：回测结果页已能从 dashboard `backtest.json` 读取 approval gate breakdown，并在最新候选卡片显示 standard/experimental gate 的逐项 PASS/FAIL。
- 已完成：回测结果页已接入 walk-forward `stability_summary`，展示稳定等级、建议 gate 模式、模型共识率、特征族集中度、正交因子占比、内存失败次数和阻断原因。

Validation Commands:

```powershell
python -m py_compile D:\Playground\freqtrade-local\apps\desktop\control_center_gui.py
cd D:\Playground\freqtrade-local\site\dashboard
cmd /c npm run build
```

## Milestone 7: 云端实盘保护

目标：云端策略更新在有持仓时更安全。

Acceptance Criteria:

- 同步前读取云端持仓摘要。
- 有持仓时不强制破坏当前仓位。
- 支持“只更新下一轮配置”或“延迟重启”。
- 同步报告明确写出保护动作。
- 已完成：只读服务器探测 `probe_openclaw_server_status.py` 已接入 Freqtrade `/status`，输出 `open_trade_check`，包含持仓数量、币种、方向、杠杆、浮盈、开仓时间和总浮盈。
- 已完成：dashboard 发布和回测结果页已读取 `open_trade_check`，实盘只读摘要展示持仓浮盈、多空方向、杠杆和开仓时间。

Validation Commands:

```powershell
python D:\Playground\freqtrade-local\scripts\workflows\probe_openclaw_server_status.py
Get-Content D:\Playground\freqtrade-local\reports\openclaw-server-status-latest.json
```

## Milestone 8: Git 安全和公开展示

目标：代码、文档和公开展示同步，但不泄露敏感信息。

Acceptance Criteria:

- GitHub 只同步源码、文档、公开静态资源。
- 不提交 `reports/`、`dashboard-data/`、`backups/`、`user_data/backtest_cache/`、回测 zip、交易密钥。
- README 和项目介绍保持与当前功能一致。
- 已完成：`.gitignore` 已补充忽略 `dashboard-data/`、`backups/`、`user_data/backtest_cache/`、本地 debug runtime policy 和 `config.openclaw-auto.before-*.json`。

Validation Commands:

```powershell
git status --short
git diff --stat
```
