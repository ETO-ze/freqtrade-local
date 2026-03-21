# OpenClaw + Freqtrade Local Workspace

A local crypto-quant workspace that combines:

- OpenClaw-driven multi-model factor training
- robust pair screening and candidate rotation
- automatic Freqtrade candidate backtesting
- gated promotion into an OKX dry-run bot
- a read-only dashboard for model and screening visibility

This repo is the local workspace layer. It is designed to live next to an OpenClaw checkout and use the OpenClaw scripts as the automation engine.

## What This Project Solves

Instead of manually training factors, copying pairlists, and rerunning backtests, this workspace lets you:

1. Continuously train local factor models in the background
2. Aggregate multiple tree-based models into a best-model view
3. Screen tradable, observe, and pause buckets
4. Build a candidate Freqtrade config automatically
5. Backtest the candidate config before promotion
6. Update the active OKX dry-run config only when gates pass

## Screenshots

### Dashboard Overview

![Dashboard Overview](assets/dashboard-overview.png)

### Best Model View

![Best Model View](assets/dashboard-best-model.png)

## Core Components

### 1. Background factor daemon

Runs the local OpenClaw workflow on a loop.

- multi-model factor training
- robust screening
- candidate config generation
- automatic backtesting
- promotion gating

### 2. Read-only dashboard

The Streamlit dashboard shows:

- candidate profit and drawdown snapshot
- current tradable / observe / pause buckets
- best-model ranking
- top factor importance
- historical model reports
- approval and strategy update reports

### 3. Freqtrade OKX dry-run bot

The active dry-run bot only uses the last approved config.

This keeps live rotation logic separate from:

- local experiments
- candidate configs
- one-off backtests

## Dependency Layout

This workspace expects a sibling OpenClaw checkout at:

```text
../openclaw
```

The local launchers and control scripts call OpenClaw workflow scripts from that folder.

## Main Features

- Continuous local factor training via background daemon
- Tree, random forest, LightGBM, and histogram gradient boosting aggregation
- Best-model selection report
- Candidate pair rotation for OKX futures dry-run
- Automatic candidate backtesting
- Promotion gate before updating active Freqtrade config
- Telegram summary notifications
- Local control center and one-click launchers

## Quick Start

### Option 1: use the control center

Open:

- `OpenClaw Control Center.cmd`

This gives you a local menu for:

- starting the factor daemon
- stopping the factor daemon
- launching the dashboard
- starting the Freqtrade auto bot
- opening reports and logs

### Option 2: use the direct launchers

- `Start OpenClaw Factor Daemon.cmd`
- `Launch Factor Dashboard.cmd`
- `Start Freqtrade Auto Bot.cmd`

## Main Files

### Workspace layer

- `factor_lab.py`
- `OPENCLAW_FREQTRADE_GUIDE.md`
- `openclaw-control-center.ps1`
- `start-openclaw-factor-daemon.ps1`
- `start-openclaw-auto-bot.ps1`

### OpenClaw workflow layer

- `../openclaw/scripts/freqtrade-daily-ml-screen.ps1`
- `../openclaw/scripts/freqtrade-factor-daemon.ps1`
- `../openclaw/scripts/freqtrade-backtest-openclaw-auto.ps1`
- `../openclaw/scripts/freqtrade-sync-screen-to-config.ps1`

## Security

Real secrets and runtime files are excluded from version control.

Not tracked:

- live Telegram bot token / chat id
- OKX API credentials
- local runtime configs
- local market data
- backtest result zips
- sqlite databases
- local reports and logs

Use the included examples instead:

- `openclaw.notification.example.json`
- `user_data/config.example.json`
- `user_data/config.openclaw-auto.example.json`

## Current Workflow

```text
OpenClaw factor daemon
  -> train multiple local models
  -> aggregate factor importance
  -> screen tradable / observe / pause buckets
  -> build candidate Freqtrade config
  -> backtest candidate config
  -> if gates pass, promote candidate
  -> active OKX dry-run bot keeps running on last approved config
```

## Local Dashboard

Start with:

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\Documents\Playground\freqtrade-local\start-factor-lab.ps1
```

Then open:

- [http://127.0.0.1:8501](http://127.0.0.1:8501)

## Freqtrade Dry-Run Bot

Start with:

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\Documents\Playground\freqtrade-local\start-openclaw-auto-bot.ps1
```

Bot API:

- [http://127.0.0.1:8081](http://127.0.0.1:8081)

## Documentation

- `OPENCLAW_FREQTRADE_GUIDE.md`
- `OPENCLAW_AUTO_SYNC.md`
- `OPENCLAW_WORKFLOW.md`
- `ML_TRAINING.md`
- `FACTOR_LAB.md`
