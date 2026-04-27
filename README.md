# OpenClaw + Freqtrade Local Workspace

![OpenClaw + Freqtrade Icon](assets/openclaw-freqtrade-icon.png)

[English](README.md) | [中文](README.zh-CN.md)

Local quantitative trading workspace built around `OpenClaw` and `Freqtrade`.

- `OpenClaw` handles factor screening, model training, approval, and automation.
- `Freqtrade` handles dry-run execution and server-side bot runtime.
- Altcoin research and mainstream research are isolated by config, ports, databases, and containers.

See also:
- [Project Overview (EN)](PROJECT_OVERVIEW.md)
- [Project Overview (中文)](PROJECT_OVERVIEW.zh-CN.md)

## Public Entry Points

- Landing page: [https://duskrain.cn](https://duskrain.cn)
- Vue dashboard: [https://duskrain.cn/dashboard/](https://duskrain.cn/dashboard/)
- Blog: [https://blog.duskrain.cn](https://blog.duskrain.cn)
- Protected Freqtrade UI: [https://www.duskrain.cn](https://www.duskrain.cn)

## Current Architecture

### Local research lane
- Dynamic altcoin universe builder
- Robust screen
- Tree-model training (`tree`, `rf`, `hgb`, `xgb`)
- Candidate backtest
- Approval gate
- Optional server sync

### Server execution lane
- Freqtrade bot runtime
- HTTPS + Authenticator protected UI
- Public read-only dashboard data

## Current Automation Layout

### `stable`
- Full formal screening lane
- Market data refresh enabled
- Dynamic universe enabled
- Current dynamic universe width: `top_n = 15`
- Auto backtest timerange mode: `auto`

### `fast`
- Lightweight screening lane
- No market data download
- Dynamic universe enabled
- Current dynamic universe width: `top_n = 20`
- No auto backtest, no promotion

### `evolution`
- Manual research lane only

### `autotune`
- Low-frequency runtime tuning lane

## Stable Promotion Gate

Current stable gate:
- Profit `>= 15%`
- Profit factor `>= 1.9`
- Max drawdown `<= 8.5%`
- Sortino `>= 7`
- Calmar `>= 45`
- Trades `>= 180`
- Trade-count bypass only when profit `>= 18%`

## Screenshots

### Dashboard Overview
![Dashboard Overview](assets/dashboard-overview-20260328.png)

### Control Center GUI
![Control Center GUI](assets/control-center-gui-20260328.png)

## Quick Start

### GUI Control Center

Open:
- [OpenClaw Control Center GUI.cmd](OpenClaw%20Control%20Center%20GUI.cmd)

Main actions:
- Start or stop `fast`
- Start or stop `stable`
- Start or stop `evolution`
- Start or stop `autotune`
- Open dashboard, reports, and daemon logs
- Manually sync the current runtime to the server

### Local dashboard

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\Documents\Playground\freqtrade-local\start-factor-lab.ps1
```

Open:
- [http://127.0.0.1:8501](http://127.0.0.1:8501)

### Strategy debug lab

```powershell
cmd /c "C:\Users\Administrator\Documents\Playground\freqtrade-local\Launch Strategy Debug Lab.cmd"
```

Open:
- [http://127.0.0.1:8502](http://127.0.0.1:8502)

## Main Commands

### Daemons

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

Autotune:
```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\Documents\Playground\freqtrade-local\start-openclaw-factor-daemon-autotune.ps1
```

### Bots

Alt bot:
```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\Documents\Playground\freqtrade-local\start-openclaw-auto-bot.ps1
```

Mainstream bot:
```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\Documents\Playground\freqtrade-local\start-mainstream-auto-bot.ps1
```

## Key Files

Workspace:
- [factor_lab.py](factor_lab.py)
- [strategy_debug_lab.py](strategy_debug_lab.py)
- [start-openclaw-control-center-gui.py](start-openclaw-control-center-gui.py)
- [runtime_state.py](runtime_state.py)

Dynamic-universe pipeline:
- [build_dynamic_alt_universe.py](build_dynamic_alt_universe.py)
- [refresh_alt_market_data.ps1](refresh_alt_market_data.ps1)
- [compare_dynamic_universe_topn.ps1](compare_dynamic_universe_topn.ps1)
- Companion local workflow script: `../openclaw/scripts/freqtrade-daily-ml-screen.ps1`

Strategies:
- [user_data/strategies/AlternativeHunter.py](user_data/strategies/AlternativeHunter.py)
- [user_data/strategies/MainstreamHunter.py](user_data/strategies/MainstreamHunter.py)

## Security

Not committed:
- Exchange API credentials
- Telegram token / chat id
- Server sync local secrets
- Local market data
- Reports and logs
- Backtest result zips
- SQLite databases

Template files:
- [openclaw.notification.example.json](openclaw.notification.example.json)
- [user_data/config.example.json](user_data/config.example.json)
- [user_data/config.openclaw-auto.example.json](user_data/config.openclaw-auto.example.json)
- [server.openclaw-sync.example.json](server.openclaw-sync.example.json)

## Documentation

- [Project Overview (EN)](PROJECT_OVERVIEW.md)
- [Project Overview (中文)](PROJECT_OVERVIEW.zh-CN.md)
- [OPENCLAW_FREQTRADE_GUIDE.md](OPENCLAW_FREQTRADE_GUIDE.md)
- [STRATEGY_DEBUG_LAB.md](STRATEGY_DEBUG_LAB.md)
- [ALTERNATIVEHUNTER_TUNING_GUIDE_CN.md](ALTERNATIVEHUNTER_TUNING_GUIDE_CN.md)
- [ML_TRAINING.md](ML_TRAINING.md)
- [FACTOR_LAB.md](FACTOR_LAB.md)
