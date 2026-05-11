<h1 align="center">OpenClaw + Freqtrade 本地量化交易控制平台</h1>

<p align="center">
  <img src="assets/openclaw-freqtrade-icon.png" alt="OpenClaw + Freqtrade" width="160" />
</p>

<p align="center">
  本地因子研究、动态山寨币筛选、Freqtrade 云端执行、只读实盘看板。
</p>

<p align="center">
  <img src="https://img.shields.io/badge/OpenClaw-%E5%9B%A0%E5%AD%90%E5%BC%95%E6%93%8E-38bdf8?style=for-the-badge" alt="OpenClaw 因子引擎" />
  <img src="https://img.shields.io/badge/Freqtrade-%E5%AE%9E%E7%9B%98%E6%9C%BA%E5%99%A8%E4%BA%BA-22c55e?style=for-the-badge" alt="Freqtrade 实盘机器人" />
  <img src="https://img.shields.io/badge/%E7%AD%96%E7%95%A5-AlternativeHunter-f97316?style=for-the-badge" alt="AlternativeHunter 策略" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776ab?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Vue-3-42b883?style=for-the-badge&logo=vuedotjs&logoColor=white" alt="Vue 3" />
  <img src="https://img.shields.io/badge/Docker-%E4%BA%91%E7%AB%AF%E8%BF%90%E8%A1%8C-2496ed?style=for-the-badge&logo=docker&logoColor=white" alt="Docker 云端运行" />
  <img src="https://img.shields.io/badge/OKX-USDT%20%E5%90%88%E7%BA%A6-111827?style=for-the-badge" alt="OKX USDT 合约" />
</p>

<p align="center">
  <a href="https://duskrain.cn">
    <img src="https://img.shields.io/badge/%E9%A6%96%E9%A1%B5-%E8%AE%BF%E9%97%AE%E7%BD%91%E7%AB%99-0ea5e9?style=for-the-badge" alt="访问首页" />
  </a>
  <a href="https://duskrain.cn/dashboard/">
    <img src="https://img.shields.io/badge/%E7%9C%8B%E6%9D%BF-%E5%8F%AA%E8%AF%BB%E7%9B%91%E6%8E%A7-06b6d4?style=for-the-badge" alt="只读看板" />
  </a>
  <a href="README.md">
    <img src="https://img.shields.io/badge/English-README-ef4444?style=for-the-badge" alt="English README" />
  </a>
</p>

<p align="center">
  <a href="README.md">English</a> | <a href="README.zh-CN.md">中文</a>
</p>

OpenClaw + Freqtrade 是一套“本地研究 + 云端执行”的个人量化交易控制平台。本地机器负责行情回补、动态山寨币池筛选、多模型因子训练、回测、审批和运行时策略配置生成；服务器负责运行受保护的 Freqtrade 机器人，并对外展示只读看板。

这个仓库更接近个人量化研究与自动化工作台，不是开箱即用的交易信号服务。

## 项目新介绍

这个项目已经从“脚本型工作区”升级成“本地量化交易控制平台”。

- 本地链路：刷新并缓存行情数据，生成动态山寨币池，训练因子模型，执行回测和审批，生成 active 配置与运行时策略。
- 云端链路：运行 Freqtrade，接收通过审批的 active 配置，必要时重启机器人，并发布只读运行状态和持仓快照。
- 看板链路：展示已批准因子、当前 active 模型、回测指标、实盘 Bot 状态、服务器同步状态、告警和项目路线标记。
- 总控链路：桌面 GUI 集中处理后台任务控制、本地看板启动、服务器同步、报告查看和安全 GitHub 同步。

## 项目亮点

- 动态山寨币池：结合 OKX 合约本地数据、成交量、流动性、市值过滤、波动率、资金费率风险和 BTC/ETH 市场状态。
- 多模型因子训练：支持树模型、随机森林、HistGradientBoosting、XGBoost，并预留 GPU 工作流接口。
- `AlternativeHunter` 山寨策略：接入模型选币、运行时策略、方向偏置、仓位缩放、杠杆上限和波动率目标。
- Promotion 审批门槛：检查收益、利润因子、胜率、回撤、交易次数、历史优秀因子和稳定性评分。
- 云端执行链路：Freqtrade 实盘运行、HTTPS 访问、Authenticator 认证和服务器同步保护。
- Vue 只读看板：展示 active 因子、回测详情、实盘 Bot 状态、告警、已批准因子历史和 roadmap 标记。
- 本地 GUI 总控：启动/停止后台模型任务、打开报告、同步服务器、一键安全同步 GitHub。

## 公开入口

- 首页：[https://duskrain.cn](https://duskrain.cn)
- 只读看板：[https://duskrain.cn/dashboard/](https://duskrain.cn/dashboard/)
- 回测结果页：[https://duskrain.cn/dashboard/backtest](https://duskrain.cn/dashboard/backtest)
- 受保护 Freqtrade 入口：[https://www.duskrain.cn](https://www.duskrain.cn)
- 博客占位页：[https://blog.duskrain.cn](https://blog.duskrain.cn)

## 截图

### 网站首页
![网站首页](assets/landing-home-20260510.png)

### Dashboard 总览
![Dashboard 总览](assets/dashboard-overview-20260510.png)

### 回测结果详情
![回测结果详情](assets/dashboard-backtest-20260510.png)

### 本地 GUI 总控
![本地 GUI 总控](assets/control-center-gui-20260328.png)

## 系统架构

```mermaid
flowchart LR
    A[本地行情缓存] --> B[动态山寨币池]
    B --> C[Robust Screen]
    C --> D[多模型因子训练]
    D --> E[候选回测]
    E --> F[审批门槛 + 稳定性评分]
    F -->|通过| G[运行时策略 + active 配置]
    G --> H[同步服务器]
    H --> I[云端 Freqtrade Bot]
    I --> J[只读看板数据]
    F --> K[已批准因子历史]
    K --> J
```

## 当前工作流

### `fast`

- 轻量筛选链路。
- 用于更频繁地观察动态币池和模型摘要。
- 不自动 promotion，不直接改云端实盘。

### `stable`

- 正式筛选和 promotion 链路。
- 刷新行情、生成动态币池、训练多模型、回测候选、执行审批 gate，并在通过后同步云端。
- 接入市值/流动性过滤，以及 BTC/ETH 市场状态。

### `autotune`

- 低频运行时参数推演。
- 只有通过审批后才影响策略侧阈值或运行时策略。

### `evolution`

- 手动研究链路。
- 默认不进入自动化主流程，避免长时间或高噪声实验影响 stable promotion。

## 因子与模型逻辑

当前因子训练不是单一模型选币，而是分层决策：

- 市场状态：用 BTC/ETH 趋势和波动判断 risk-on、neutral、risk-off。
- 横截面排名：比较山寨币之间的相对强弱、成交量、动量、流动性和市值质量。
- 时间序列确认：检查单币趋势确认、EMA 结构、突破位置、趋势一致性和波动惩罚。
- 资金费率与 mark premium：作为风险/拥挤度因子，不再允许无限主导模型。
- 运行时仓位：由模型分数、近期分数、市场状态、波动率缩放和趋势确认共同决定仓位与杠杆上限。

## Promotion 与安全逻辑

系统不会因为出现新候选因子就直接替换当前实盘配置。候选需要通过审批门槛，并和历史已批准因子比较。

当前重点检查：

- 总收益与利润因子。
- 胜率与最大回撤。
- 交易次数下限保护。
- 高收益高风险实验通道。
- 稳定性评分：月度一致性、单币贡献集中度、回撤持续时间、多空失衡和分段表现。
- 历史最优保护：明显弱于当前 active 因子的候选不会覆盖实盘。

## Roadmap 标记

`完整独立 walk-forward 重训` 已加入项目标记。

当前状态：
- 分段稳定性评分已经接入审批 gate。

下一步计划：
- 将训练期、验证期、测试期和最近窗口拆成独立重训与独立回测。
- 汇总多段评分后再决定是否 promotion。
- 在缓存、任务队列和 promotion 行为完全验证前保持未启用。

详见：[PROJECT_ROADMAP.json](PROJECT_ROADMAP.json)

## 快速启动

### GUI 总控中心

```powershell
cmd /c "D:\Playground\freqtrade-local\launchers\OpenClaw Control Center GUI.cmd"
```

主要功能：

- 启动/停止 `fast`、`stable`、`evolution`、`autotune`。
- 打开本地看板、报告和日志目录。
- 探测服务器连通性。
- 手动同步已批准的 active 配置到服务器。
- 安全同步 GitHub，避免提交本地密钥和数据。

### 本地因子看板

```powershell
powershell -ExecutionPolicy Bypass -File D:\Playground\freqtrade-local\scripts\windows\start-factor-lab.ps1
```

打开：

- [http://127.0.0.1:8501](http://127.0.0.1:8501)

### 策略调试面板

```powershell
cmd /c "D:\Playground\freqtrade-local\launchers\Launch Strategy Debug Lab.cmd"
```

打开：

- [http://127.0.0.1:8502](http://127.0.0.1:8502)

## 常用命令

### 启动后台训练

```powershell
powershell -ExecutionPolicy Bypass -File D:\Playground\freqtrade-local\scripts\windows\start-openclaw-factor-daemon-fast.ps1
powershell -ExecutionPolicy Bypass -File D:\Playground\freqtrade-local\scripts\windows\start-openclaw-factor-daemon-stable.ps1
powershell -ExecutionPolicy Bypass -File D:\Playground\freqtrade-local\scripts\windows\start-openclaw-factor-daemon-autotune.ps1
```

### 停止后台训练

```powershell
powershell -ExecutionPolicy Bypass -File D:\Playground\freqtrade-local\scripts\windows\stop-openclaw-factor-daemon-fast.ps1
powershell -ExecutionPolicy Bypass -File D:\Playground\freqtrade-local\scripts\windows\stop-openclaw-factor-daemon-stable.ps1
powershell -ExecutionPolicy Bypass -File D:\Playground\freqtrade-local\scripts\windows\stop-openclaw-factor-daemon-autotune.ps1
```

### 同步服务器

```powershell
powershell -ExecutionPolicy Bypass -File D:\Playground\freqtrade-local\scripts\windows\sync-openclaw-runtime-to-server.ps1
```

### 云端持仓同步

服务器端 `openclaw-dashboard-status-sync.timer` 会把云端 Freqtrade 机器人状态和实盘持仓只读快照写入 `/dashboard-data/status.json`，Vue 看板会自动刷新读取。该功能已经纳入服务器同步/运行链路，GUI 不再保留单独的“安装云端持仓同步”按钮。下面命令只用于手动维护。

```powershell
powershell -ExecutionPolicy Bypass -File D:\Playground\freqtrade-local\scripts\windows\install-server-position-sync.ps1 -IntervalSeconds 60 -RunOnce
```

### 安全同步 GitHub

```powershell
powershell -ExecutionPolicy Bypass -File D:\Playground\freqtrade-local\scripts\windows\sync-github-safe.ps1
```

## 关键文件

- [apps/desktop/control_center_gui.py](apps/desktop/control_center_gui.py)：本地 GUI 总控。
- [apps/streamlit/factor_lab.py](apps/streamlit/factor_lab.py)：本地只读因子看板实现。
- [apps/streamlit/strategy_debug_lab.py](apps/streamlit/strategy_debug_lab.py)：策略回测与调试面板实现。
- [apps/streamlit/telegram_template_lab.py](apps/streamlit/telegram_template_lab.py)：Telegram 模板面板实现。
- [scripts/workflows/build_dynamic_alt_universe.py](scripts/workflows/build_dynamic_alt_universe.py)：动态山寨币池生成器。
- [scripts/workflows/evaluate_backtest_stability.py](scripts/workflows/evaluate_backtest_stability.py)：稳定性与分段回测评估器。
- [scripts/workflows/publish_dashboard_public_data.py](scripts/workflows/publish_dashboard_public_data.py)：公开看板数据发布脚本。
- [scripts/workflows/sync_openclaw_runtime_to_server.py](scripts/workflows/sync_openclaw_runtime_to_server.py)：云端同步辅助脚本。
- [user_data/strategies/AlternativeHunter.py](user_data/strategies/AlternativeHunter.py)：当前山寨主策略。
- [PROJECT_ROADMAP.json](PROJECT_ROADMAP.json)：项目标记与后续计划。
- [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md)：仓库目录结构与整理说明。

## 安全说明

仓库默认避免提交以下私密或大体积运行数据：

- 交易所 API 凭证。
- Telegram token / chat id。
- 服务器同步凭证。
- 本地行情缓存。
- 回测结果 zip。
- 报告、后台日志和 SQLite 数据库。
- 包含密钥的实盘运行配置。

示例模板：

- [openclaw.notification.example.json](openclaw.notification.example.json)
- [server.openclaw-sync.example.json](server.openclaw-sync.example.json)
- [user_data/config.example.json](user_data/config.example.json)
- [user_data/config.openclaw-auto.example.json](user_data/config.openclaw-auto.example.json)

## 风险提示

本项目用于量化研究和小资金自动化验证。加密货币合约和山寨币波动大、流动性变化快，杠杆会显著放大风险。历史回测和模型评分不能保证未来收益。
