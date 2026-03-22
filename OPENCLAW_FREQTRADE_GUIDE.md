# OpenClaw + Freqtrade Local Guide

## Overview

This workspace runs a local altcoin factor pipeline around `OpenClaw + Freqtrade`.

Main parts:

1. Fast daemon
- Interval: 20 minutes
- Purpose: refresh the local screening view quickly
- Model set: `rf`
- Candidate pool: local-wide OKX alt futures pairs with local `5m` data
- Auto backtest: disabled

2. Stable daemon
- Interval: 180 minutes
- Purpose: run the full candidate promotion workflow
- Model set: `tree,rf,hgb`
- Candidate pool: local-wide OKX alt futures pairs with local `5m` data
- Auto backtest: enabled
- Promotion rule: only update active Freqtrade config when gates pass

3. OpenClaw workflow
- Runs robust screening
- Trains local tree models in Docker
- Aggregates factors and pair rankings
- Builds candidate Freqtrade config
- Runs candidate backtest on the stable path
- Pushes summary updates to Telegram

4. Freqtrade OKX dry-run bot
- Runs the last approved strategy config in OKX futures simulation mode
- API URL: [http://127.0.0.1:8081](http://127.0.0.1:8081)

5. Read-only Factor Lab dashboard
- Shows latest model reports, pair buckets, best-model summaries, and approval output
- URL: [http://127.0.0.1:8501](http://127.0.0.1:8501)

## Current Runtime Logic

1. Fast and stable daemons now share a workflow lock.
2. If stable is running a full cycle, fast will skip instead of competing for training resources.
3. Stable is the only path allowed to promote a candidate into the active Freqtrade auto config.
4. The active dry-run bot keeps using the last approved config until a new candidate passes.

## Candidate Pool And Factor Model

Current local-wide pool config:
- [config.backtest.okx-futures-alt-local-wide.json](/Users/Administrator/Documents/Playground/freqtrade-local/user_data/config.backtest.okx-futures-alt-local-wide.json)

Current feature set includes:
- Price: `ret_1`, `ret_3`, `ret_6`, `ret_12`, `ret_24`, `price_vs_rollmean_24`
- Volatility: `volatility_12`, `volatility_24`, `volatility_ratio_12_24`, `atr_14_pct`
- Volume: `volume_ratio_6`, `volume_ratio_24`, `volume_trend_24_72`, `volume_zscore_24`
- Structure: `range_pct`, `body_pct`, `upper_wick_pct`, `lower_wick_pct`, `breakout_24`, `breakdown_24`
- Trend: `ema_8`, `ema_21`, `ema_55`, `ema_gap`, `ema_8_55_gap`, `ema_gap_slope_3`, `rsi_14`
- Recent scoring: `recent_score`, `recent_long_avg_forward_return`, `recent_short_avg_forward_return`

Training script:
- [train_alt_tree_models.py](/Users/Administrator/Documents/Playground/freqtrade-local/user_data/notebooks/train_alt_tree_models.py)

## Verified Notes

What has been verified locally:
- Fast pipeline runs successfully against the new local-wide candidate pool
- New factor fields are present in the generated ML JSON
- `tree`, `rf`, and `hgb` all work in the training container
- `lightgbm` is not installed in the current training container, so it is not part of the default live workflow
- Shared workflow locking is enabled to prevent fast and stable from training at the same time

Reference outputs:
- Fast combined JSON: [openclaw-daily-alt-ml-fast.json](/Users/Administrator/Documents/Playground/freqtrade-local/reports/openclaw-daily-alt-ml-fast.json)
- Fast best-model JSON: [openclaw-best-model-fast.json](/Users/Administrator/Documents/Playground/freqtrade-local/reports/openclaw-best-model-fast.json)
- Fast model JSON: [daily-alt-tree-model-fast.json](/Users/Administrator/Documents/Playground/freqtrade-local/user_data/reports/ml/daily-alt-tree-model-fast.json)
- Multi-model smoke test: [factor-multimodel-smoketest.json](/Users/Administrator/Documents/Playground/freqtrade-local/user_data/reports/ml/factor-multimodel-smoketest.json)

## Telegram Bot

- Name: `OpenClaw小阳`
- Username: `@opendusk_bot`
- Bot ID: `8708596011`

## Main Start Commands

Dashboard:

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\Documents\Playground\freqtrade-local\start-factor-lab.ps1
```

Fast daemon:

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\Documents\Playground\freqtrade-local\start-openclaw-factor-daemon-fast.ps1
```

Stable daemon:

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\Documents\Playground\freqtrade-local\start-openclaw-factor-daemon-stable.ps1
```

Stop fast daemon:

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\Documents\Playground\freqtrade-local\stop-openclaw-factor-daemon-fast.ps1
```

Stop stable daemon:

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\Documents\Playground\freqtrade-local\stop-openclaw-factor-daemon-stable.ps1
```

Start approved Freqtrade dry-run bot:

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\Documents\Playground\freqtrade-local\start-openclaw-auto-bot.ps1
```

GUI control center:

```powershell
py C:\Users\Administrator\Documents\Playground\freqtrade-local\start-openclaw-control-center-gui.py
```

Console control center:

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\Documents\Playground\freqtrade-local\openclaw-control-center.ps1
```

## Quick Launch Files

In [freqtrade-local](/Users/Administrator/Documents/Playground/freqtrade-local):

- [Launch Factor Dashboard.cmd](/Users/Administrator/Documents/Playground/freqtrade-local/Launch%20Factor%20Dashboard.cmd)
- [Start OpenClaw Fast Daemon.cmd](/Users/Administrator/Documents/Playground/freqtrade-local/Start%20OpenClaw%20Fast%20Daemon.cmd)
- [Start OpenClaw Stable Daemon.cmd](/Users/Administrator/Documents/Playground/freqtrade-local/Start%20OpenClaw%20Stable%20Daemon.cmd)
- [Start Freqtrade Auto Bot.cmd](/Users/Administrator/Documents/Playground/freqtrade-local/Start%20Freqtrade%20Auto%20Bot.cmd)
- [OpenClaw Control Center.cmd](/Users/Administrator/Documents/Playground/freqtrade-local/OpenClaw%20Control%20Center.cmd)
- [OpenClaw Control Center GUI.cmd](/Users/Administrator/Documents/Playground/freqtrade-local/OpenClaw%20Control%20Center%20GUI.cmd)
- [Open Reports Folder.cmd](/Users/Administrator/Documents/Playground/freqtrade-local/Open%20Reports%20Folder.cmd)

## Important Files

Workspace:
- [freqtrade-local](/Users/Administrator/Documents/Playground/freqtrade-local)

Workflow scripts:
- [freqtrade-daily-ml-screen.ps1](/Users/Administrator/Documents/Playground/openclaw/scripts/freqtrade-daily-ml-screen.ps1)
- [freqtrade-factor-daemon.ps1](/Users/Administrator/Documents/Playground/openclaw/scripts/freqtrade-factor-daemon.ps1)
- [freqtrade-robust-screen.ps1](/Users/Administrator/Documents/Playground/openclaw/scripts/freqtrade-robust-screen.ps1)

Daemon launchers:
- [start-openclaw-factor-daemon-fast.ps1](/Users/Administrator/Documents/Playground/freqtrade-local/start-openclaw-factor-daemon-fast.ps1)
- [start-openclaw-factor-daemon-stable.ps1](/Users/Administrator/Documents/Playground/freqtrade-local/start-openclaw-factor-daemon-stable.ps1)
- [stop-openclaw-factor-daemon-fast.ps1](/Users/Administrator/Documents/Playground/freqtrade-local/stop-openclaw-factor-daemon-fast.ps1)
- [stop-openclaw-factor-daemon-stable.ps1](/Users/Administrator/Documents/Playground/freqtrade-local/stop-openclaw-factor-daemon-stable.ps1)

Control center:
- [openclaw-control-center.ps1](/Users/Administrator/Documents/Playground/freqtrade-local/openclaw-control-center.ps1)
- [start-openclaw-control-center-gui.py](/Users/Administrator/Documents/Playground/freqtrade-local/start-openclaw-control-center-gui.py)

Active auto bot config:
- [config.openclaw-auto.json](/Users/Administrator/Documents/Playground/freqtrade-local/user_data/config.openclaw-auto.json)

Candidate outputs:
- [config.openclaw-candidate-fast.json](/Users/Administrator/Documents/Playground/freqtrade-local/user_data/config.openclaw-candidate-fast.json)
- [config.openclaw-candidate-stable.json](/Users/Administrator/Documents/Playground/freqtrade-local/user_data/config.openclaw-candidate-stable.json)

## Status And Logs

Daemon state directory:
- [reports/daemon](/Users/Administrator/Documents/Playground/freqtrade-local/reports/daemon)

Fast:
- [factor-daemon-fast-status.json](/Users/Administrator/Documents/Playground/freqtrade-local/reports/daemon/factor-daemon-fast-status.json)
- [factor-daemon-fast.out.log](/Users/Administrator/Documents/Playground/freqtrade-local/reports/daemon/factor-daemon-fast.out.log)
- [factor-daemon-fast.err.log](/Users/Administrator/Documents/Playground/freqtrade-local/reports/daemon/factor-daemon-fast.err.log)

Stable:
- [factor-daemon-stable-status.json](/Users/Administrator/Documents/Playground/freqtrade-local/reports/daemon/factor-daemon-stable-status.json)
- [factor-daemon-stable.out.log](/Users/Administrator/Documents/Playground/freqtrade-local/reports/daemon/factor-daemon-stable.out.log)
- [factor-daemon-stable.err.log](/Users/Administrator/Documents/Playground/freqtrade-local/reports/daemon/factor-daemon-stable.err.log)

Shared run lock:
- `C:\Users\Administrator\Documents\Playground\freqtrade-local\reports\daemon\openclaw-ml-workflow.lock`

## How To Check Health

1. Open the fast or stable status JSON.
2. Check `status`, `started_at`, `completed_at`, and `next_run_after`.
3. Read the matching `.out.log`.
4. Expected behavior:
- Fast may show `skipped` when stable is running. This is normal.
- Stable should show `running` during a full cycle and `ok` after completion.
- The dry-run bot should answer ping on [http://127.0.0.1:8081/api/v1/ping](http://127.0.0.1:8081/api/v1/ping)
