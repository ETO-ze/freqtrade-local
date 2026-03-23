# OpenClaw + Freqtrade Local Workspace

![OpenClaw + Freqtrade Icon](assets/openclaw-freqtrade-icon.png)

中文 | English

一个本地化的币圈量化工作区，用 `OpenClaw` 做后台因子筛选和流程编排，用 `Freqtrade` 做 OKX 模拟盘执行。

A local crypto-quant workspace that uses `OpenClaw` for factor screening and workflow orchestration, and `Freqtrade` for OKX dry-run execution on OKX.

项目图标文件：

- PNG: [assets/openclaw-freqtrade-icon.png](assets/openclaw-freqtrade-icon.png)
- ICO: [assets/openclaw-freqtrade-icon.ico](assets/openclaw-freqtrade-icon.ico)

Project icon files:

- PNG: [assets/openclaw-freqtrade-icon.png](assets/openclaw-freqtrade-icon.png)
- ICO: [assets/openclaw-freqtrade-icon.ico](assets/openclaw-freqtrade-icon.ico)

## 概览 | Overview

这不是单次回测脚本，而是一条持续运行的本地自动链路：

- `Fast` 负责轻量筛选
- `Stable` 负责正式多模型、自动回测、达标 promotion
- `Evolution` 保留为手动研究层
- `Freqtrade` 只运行最后一次审批通过的 active 配置

This is not a one-off backtest setup. It is a continuous local automation loop:

- `Fast` handles lightweight screening
- `Stable` handles formal multi-model training, backtests, and gated promotion
- `Evolution` is kept as a manual research layer
- `Freqtrade` runs only the last approved active config

## 截图 | Screenshots

### Dashboard Overview

![Dashboard Overview](assets/dashboard-overview.png)

### Best Model View

![Best Model View](assets/dashboard-best-model.png)

## 当前结构 | Current Runtime Structure

### 1. Fast Screening

作用：

- 高频轻量筛选
- 刷新因子视图
- 更新 `tradable / observe / pause`
- 不做自动 promotion

Purpose:

- high-frequency lightweight screening
- refreshes the local factor view
- updates `tradable / observe / pause`
- does not promote configs automatically

### 2. Stable Promotion

作用：

- 运行正式多模型流程
- 自动回测候选配置
- 达标后更新 active Freqtrade 配置
- 这是 live 自动链的核心

当前 live 模型组合：

- `tree`
- `rf`
- `hgb`

Purpose:

- runs the formal multi-model workflow
- backtests candidate configs automatically
- promotes into the active Freqtrade config only when gates pass
- this is the production automation path

Current live model set:

- `tree`
- `rf`
- `hgb`

### 3. Evolution Research

作用：

- 研究更优因子组合和 profile
- 只做离线/手动探索
- 不直接接入 live promotion

Purpose:

- explore better feature subsets and model profiles
- manual / offline research only
- does not directly control live promotion

## 自动化链路 | Automation Flow

```text
OpenClaw Fast
  -> lightweight screening
  -> local factor refresh
  -> tradable / observe / pause buckets

OpenClaw Stable
  -> robust screen
  -> local multi-model training
  -> candidate config generation
  -> candidate backtest
  -> if gates pass, promote candidate
  -> restart / reuse Freqtrade dry-run bot on approved config

Freqtrade Auto Bot
  -> runs only the last approved active config
```

## 开机自启动 | Startup Behavior

Windows 登录后会通过统一启动项完成：

1. 启动 OpenClaw 本体代理
2. 启动 Docker Desktop
3. 启动 `stable`
4. 启动 `fast`
5. 启动 `Freqtrade` auto bot

On Windows login, the unified startup entry will:

1. start the OpenClaw proxy
2. start Docker Desktop
3. start `stable`
4. start `fast`
5. start the `Freqtrade` auto bot

关键入口 | Main entry:

- [start-openclaw-on-login.ps1](start-openclaw-on-login.ps1)
- [Start OpenClaw On Login.cmd](Start%20OpenClaw%20On%20Login.cmd)

## 主要功能 | Main Features

- 本地后台树模型训练
- 宽池山寨币筛选
- 多模型 best-model 排名
- 候选配置自动生成
- 候选策略自动回测
- 审批达标后自动更新 active 配置
- Telegram 摘要推送
- GUI / 控制台总控
- 开机自动接管 OpenClaw + Freqtrade

- local background tree-model training
- broad altcoin candidate screening
- multi-model best-model ranking
- automatic candidate config generation
- automatic candidate backtesting
- gated promotion into the active config
- Telegram summary pushes
- GUI / console control center
- startup takeover for OpenClaw + Freqtrade

## 快速开始 | Quick Start

### 方式一：总控中心 | Option 1: Control Center

打开：

- [OpenClaw Control Center.cmd](OpenClaw%20Control%20Center.cmd)
- [OpenClaw Control Center GUI.cmd](OpenClaw%20Control%20Center%20GUI.cmd)

你可以在里面：

- 启动/停止 `fast`
- 启动/停止 `stable`
- 手动启动/停止 `evolution`
- 启动 `Freqtrade` auto bot
- 打开看板、日志、报告和说明书

From the control center you can:

- start/stop `fast`
- start/stop `stable`
- manually start/stop `evolution`
- start the `Freqtrade` auto bot
- open the dashboard, logs, reports, and guide

### 方式二：直接脚本 | Option 2: Direct Scripts

Fast:

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\Documents\Playground\freqtrade-local\start-openclaw-factor-daemon-fast.ps1
```

Stable:

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\Documents\Playground\freqtrade-local\start-openclaw-factor-daemon-stable.ps1
```

Evolution:

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\Documents\Playground\freqtrade-local\start-openclaw-factor-daemon-evolution.ps1
```

Freqtrade bot:

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\Documents\Playground\freqtrade-local\start-openclaw-auto-bot.ps1
```

## 看板和 Bot | Dashboard and Bot

Dashboard:

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\Documents\Playground\freqtrade-local\start-factor-lab.ps1
```

- [http://127.0.0.1:8501](http://127.0.0.1:8501)

Freqtrade API:

- [http://127.0.0.1:8081](http://127.0.0.1:8081)

## 关键文件 | Key Files

### Workspace Layer

- [factor_lab.py](factor_lab.py)
- [OPENCLAW_FREQTRADE_GUIDE.md](OPENCLAW_FREQTRADE_GUIDE.md)
- [openclaw-control-center.ps1](openclaw-control-center.ps1)
- [start-openclaw-control-center-gui.py](start-openclaw-control-center-gui.py)
- [start-openclaw-on-login.ps1](start-openclaw-on-login.ps1)

### Daemon Launchers

- [start-openclaw-factor-daemon-fast.ps1](start-openclaw-factor-daemon-fast.ps1)
- [start-openclaw-factor-daemon-stable.ps1](start-openclaw-factor-daemon-stable.ps1)
- [start-openclaw-factor-daemon-evolution.ps1](start-openclaw-factor-daemon-evolution.ps1)
- [stop-openclaw-factor-daemon-fast.ps1](stop-openclaw-factor-daemon-fast.ps1)
- [stop-openclaw-factor-daemon-stable.ps1](stop-openclaw-factor-daemon-stable.ps1)
- [stop-openclaw-factor-daemon-evolution.ps1](stop-openclaw-factor-daemon-evolution.ps1)

### OpenClaw Workflow Layer

- [freqtrade-daily-ml-screen.ps1](../openclaw/scripts/freqtrade-daily-ml-screen.ps1)
- [freqtrade-factor-daemon.ps1](../openclaw/scripts/freqtrade-factor-daemon.ps1)
- [freqtrade-backtest-openclaw-auto.ps1](../openclaw/scripts/freqtrade-backtest-openclaw-auto.ps1)
- [freqtrade-sync-screen-to-config.ps1](../openclaw/scripts/freqtrade-sync-screen-to-config.ps1)

## 安全 | Security

真实敏感信息不会上传到仓库。

不会跟踪：

- Telegram bot token / chat id
- OKX API credentials
- 本地运行时配置
- 本地行情数据
- 回测结果 zip
- sqlite 数据库
- 本地日志和报告

Real secrets and runtime artifacts are excluded from version control.

Not tracked:

- Telegram bot token / chat id
- OKX API credentials
- local runtime configs
- local market data
- backtest result zips
- sqlite databases
- local logs and reports

模板文件 | Example templates:

- [openclaw.notification.example.json](openclaw.notification.example.json)
- [config.example.json](user_data/config.example.json)
- [config.openclaw-auto.example.json](user_data/config.openclaw-auto.example.json)

## 文档 | Documentation

- [OPENCLAW_FREQTRADE_GUIDE.md](OPENCLAW_FREQTRADE_GUIDE.md)
- [OPENCLAW_AUTO_SYNC.md](OPENCLAW_AUTO_SYNC.md)
- [OPENCLAW_WORKFLOW.md](OPENCLAW_WORKFLOW.md)
- [ML_TRAINING.md](ML_TRAINING.md)
- [FACTOR_LAB.md](FACTOR_LAB.md)
