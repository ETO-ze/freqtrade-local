# OpenClaw + Freqtrade 本地量化交易控制平台

OpenClaw + Freqtrade 是一个面向个人量化实验的本地控制平台。项目把因子训练、币池筛选、回测审批、参数推演、云端同步和交易机器人运行拆成相互隔离的模块，目标是在不频繁手动干预的情况下，持续寻找更适合当前山寨币市场环境的策略配置。

## 当前定位

本项目不是单一策略脚本，而是一套围绕 Freqtrade 的本地量化工作流：

- 本地负责：数据回补、动态币池筛选、多模型因子训练、回测、审批、参数推演、看板展示。
- 云端负责：运行 Freqtrade、执行交易、暴露只读状态、接收通过审批后的配置同步。
- GUI 负责：启动/停止本地后台任务、查看状态、打开看板、手动同步服务器、同步 GitHub。

## 核心能力

### 1. 动态山寨币池

系统会定期根据近期市场数据筛选候选币，避免长期固定在一批流动性衰退的币种上。Stable 流程更偏正式筛选，Fast 流程更偏轻量观察。

### 2. 多模型因子训练

当前支持树模型、随机森林、HistGradientBoosting、XGBoost 等模型组合。模型会根据价格、波动、量能、结构、BTC/ETH 相对强弱、资金费率偏移等特征生成候选交易因子。

### 3. 回测审批与保护

候选因子不会直接覆盖正在使用的配置。系统会先回测，再按 gate 条件判断是否进入审批历史。当前逻辑倾向优先保留历史表现更强的因子，避免没有更好结果时频繁替换。

### 4. 高收益高风险实验通道

山寨策略已接入高收益高风险模式。该模式会在模型分数较高时提高杠杆，但仍通过仓位、最大开仓数、止损和回撤约束控制风险。它适合小资金测试，不应直接视为稳健实盘方案。

### 5. 本地与云端分离

本地机器可以承担较重的训练、回测和筛选任务；云端只负责交易执行。这样可以降低服务器资源压力，也避免训练任务影响实盘机器人稳定性。

## 运行入口

常用入口：

- GUI 总控：`OpenClaw Control Center GUI.cmd`
- 网页看板：`factor_lab.py`
- 策略调试：`strategy_debug_lab.py`
- Telegram 模板：`telegram_template_lab.py`
- 启动 Fast：`start-openclaw-factor-daemon-fast.ps1`
- 启动 Stable：`start-openclaw-factor-daemon-stable.ps1`
- 启动 Evolution：`start-openclaw-factor-daemon-evolution.ps1`
- 启动 Autotune：`start-openclaw-factor-daemon-autotune.ps1`
- 同步云端：`sync-openclaw-runtime-to-server.ps1`
- 同步 GitHub：`sync-github-safe.ps1`

## 当前策略状态

主策略为 `AlternativeHunter`。它面向山寨币永续合约，重点不是高频交易，而是通过模型筛选币池、趋势动量、风险规避和动态杠杆，在波动环境中寻找收益机会。

当前运行原则：

- 没有新因子达标时，不主动替换现有 active 配置。
- 新因子收益接近历史最优时，进一步比较胜率和回撤。
- 新因子收益明显低于历史最优时，保留历史表现更强的配置。
- 云端如果存在持仓，同步策略时应优先避免强制重启造成异常。

## 风险说明

本项目用于量化研究和小资金验证。山寨币波动大、滑点高、流动性变化快，历史回测不能代表未来收益。高杠杆模式只适合实验账户，不建议直接用于大资金。

## 后续优化方向

- 将 GUI 从 Tkinter 逐步升级为独立本地 Web 控制台。
- 将训练任务从脚本调度迁移到统一任务队列。
- 增强 long history cache，减少重复回补和重复特征计算。
- 增加实盘交易结果反馈，让模型可以分析每笔交易成败。
- 增强服务器只读状态同步，减少本地与云端状态不一致。
## Project Marker: Independent Walk-forward Retraining

- Status: planned, not enabled.
- Current state: segmented stability scoring is already connected to the approval gate.
- Next step: split train / validation / test / recent windows into independent retraining and independent backtests, then merge the scores before promotion.
- Safety note: this marker is display-only and does not change cloud trading behavior.
