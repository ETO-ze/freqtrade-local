# OpenClaw + Freqtrade Local Guide

## What It Does

This workspace currently has four main pieces:

1. Background factor daemon
Runs local multi-model factor training, robust screening, candidate config generation, automatic backtesting, and promotion gating.

2. OpenClaw workflow
Handles screening, model aggregation, best-model selection, Telegram summary push, and Freqtrade config updates when the candidate backtest passes the gate.

3. Freqtrade OKX dry-run bot
Runs the approved strategy and pairlist in OKX futures simulation mode.

4. Read-only Factor Lab dashboard
Shows the latest model data, pair buckets, best model, approval report, and historical ML reports.

## Recommended Daily Usage

1. Start the background factor daemon.
2. Keep the dashboard open only for viewing results.
3. Let OpenClaw update reports and candidate configs automatically.
4. Let Freqtrade auto dry-run keep using the last approved config.

## Quick Launch Files

These files are in:
[freqtrade-local](/Users/Administrator/Documents/Playground/freqtrade-local)

- [Launch Factor Dashboard.cmd](/Users/Administrator/Documents/Playground/freqtrade-local/Launch%20Factor%20Dashboard.cmd)
- [Start OpenClaw Factor Daemon.cmd](/Users/Administrator/Documents/Playground/freqtrade-local/Start%20OpenClaw%20Factor%20Daemon.cmd)
- [Stop OpenClaw Factor Daemon.cmd](/Users/Administrator/Documents/Playground/freqtrade-local/Stop%20OpenClaw%20Factor%20Daemon.cmd)
- [Start Freqtrade Auto Bot.cmd](/Users/Administrator/Documents/Playground/freqtrade-local/Start%20Freqtrade%20Auto%20Bot.cmd)
- [Open Reports Folder.cmd](/Users/Administrator/Documents/Playground/freqtrade-local/Open%20Reports%20Folder.cmd)

## Core Start Commands

### 1. Start the read-only dashboard

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\Documents\Playground\freqtrade-local\start-factor-lab.ps1
```

Dashboard URL:
[http://127.0.0.1:8501](http://127.0.0.1:8501)

### 2. Start the background factor daemon

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\Documents\Playground\freqtrade-local\start-openclaw-factor-daemon.ps1
```

### 3. Stop the background factor daemon

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\Documents\Playground\freqtrade-local\stop-openclaw-factor-daemon.ps1
```

### 4. Start the approved Freqtrade dry-run bot

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\Documents\Playground\freqtrade-local\start-openclaw-auto-bot.ps1
```

Bot API:
[http://127.0.0.1:8081](http://127.0.0.1:8081)

## Main Workflow Files

### Freqtrade workspace

- Root: [freqtrade-local](/Users/Administrator/Documents/Playground/freqtrade-local)
- Read-only dashboard: [factor_lab.py](/Users/Administrator/Documents/Playground/freqtrade-local/factor_lab.py)
- Dashboard launcher: [start-factor-lab.ps1](/Users/Administrator/Documents/Playground/freqtrade-local/start-factor-lab.ps1)
- Background daemon starter: [start-openclaw-factor-daemon.ps1](/Users/Administrator/Documents/Playground/freqtrade-local/start-openclaw-factor-daemon.ps1)
- Background daemon stopper: [stop-openclaw-factor-daemon.ps1](/Users/Administrator/Documents/Playground/freqtrade-local/stop-openclaw-factor-daemon.ps1)
- Auto bot starter: [start-openclaw-auto-bot.ps1](/Users/Administrator/Documents/Playground/freqtrade-local/start-openclaw-auto-bot.ps1)

### OpenClaw scripts

- Main workflow: [freqtrade-daily-ml-screen.ps1](/Users/Administrator/Documents/Playground/openclaw/scripts/freqtrade-daily-ml-screen.ps1)
- Background loop daemon: [freqtrade-factor-daemon.ps1](/Users/Administrator/Documents/Playground/openclaw/scripts/freqtrade-factor-daemon.ps1)
- Candidate backtest: [freqtrade-backtest-openclaw-auto.ps1](/Users/Administrator/Documents/Playground/openclaw/scripts/freqtrade-backtest-openclaw-auto.ps1)
- Screen-to-config sync: [freqtrade-sync-screen-to-config.ps1](/Users/Administrator/Documents/Playground/openclaw/scripts/freqtrade-sync-screen-to-config.ps1)
- Robust screen: [freqtrade-robust-screen.ps1](/Users/Administrator/Documents/Playground/openclaw/scripts/freqtrade-robust-screen.ps1)

## Important Config Paths

- Approved auto config: [config.openclaw-auto.json](/Users/Administrator/Documents/Playground/freqtrade-local/user_data/config.openclaw-auto.json)
- Candidate config: [config.openclaw-candidate.json](/Users/Administrator/Documents/Playground/freqtrade-local/user_data/config.openclaw-candidate.json)
- Telegram config: [openclaw.notification.json](/Users/Administrator/Documents/Playground/freqtrade-local/openclaw.notification.json)

## Main Reports

- Combined daily report: [openclaw-daily-alt-ml.md](/Users/Administrator/Documents/Playground/freqtrade-local/reports/openclaw-daily-alt-ml.md)
- Combined daily JSON: [openclaw-daily-alt-ml.json](/Users/Administrator/Documents/Playground/freqtrade-local/reports/openclaw-daily-alt-ml.json)
- Best model report: [openclaw-best-model-latest.md](/Users/Administrator/Documents/Playground/freqtrade-local/reports/openclaw-best-model-latest.md)
- Best model JSON: [openclaw-best-model-latest.json](/Users/Administrator/Documents/Playground/freqtrade-local/reports/openclaw-best-model-latest.json)
- Strategy update report: [openclaw-strategy-update-latest.md](/Users/Administrator/Documents/Playground/freqtrade-local/reports/openclaw-strategy-update-latest.md)
- Approval report: [openclaw-auto-approval-latest.md](/Users/Administrator/Documents/Playground/freqtrade-local/reports/openclaw-auto-approval-latest.md)
- Backtest summary JSON: [openclaw-auto-backtest-latest.json](/Users/Administrator/Documents/Playground/freqtrade-local/reports/openclaw-auto-backtest-latest.json)

## Daemon State Files

These are created in:
[reports/daemon](/Users/Administrator/Documents/Playground/freqtrade-local/reports/daemon)

- Status: [factor-daemon-status.json](/Users/Administrator/Documents/Playground/freqtrade-local/reports/daemon/factor-daemon-status.json)
- Log: [factor-daemon.log](/Users/Administrator/Documents/Playground/freqtrade-local/reports/daemon/factor-daemon.log)
- PID: [factor-daemon.pid](/Users/Administrator/Documents/Playground/freqtrade-local/reports/daemon/factor-daemon.pid)
- Lock: [factor-daemon.lock](/Users/Administrator/Documents/Playground/freqtrade-local/reports/daemon/factor-daemon.lock)

## Current Logic

1. The daemon calls the OpenClaw workflow on a loop.
2. OpenClaw trains multiple local models.
3. OpenClaw aggregates factors and pair rankings.
4. OpenClaw picks a best model and writes the report.
5. OpenClaw builds a candidate Freqtrade config.
6. The candidate config is backtested automatically.
7. Only if the gate passes, the approved auto config is updated.
8. The running OKX dry-run bot keeps using the last approved config.

## Notes

- The dashboard is now read-only.
- Training and screening are handled by OpenClaw in the background.
- The daemon default interval is 30 minutes.
- The dry-run bot stays separate from the main config.
