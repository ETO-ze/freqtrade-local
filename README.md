# OpenClaw + Freqtrade Local Workspace

This folder contains a local Freqtrade workspace that has been extended with:

- a read-only factor dashboard
- OpenClaw-driven multi-model factor training and screening
- automatic candidate backtesting and promotion gating
- an OKX dry-run bot that only uses the last approved config
- local launchers, shortcuts, and control scripts

## Dependency Layout

This workspace assumes it lives beside an OpenClaw checkout at:

- `../openclaw`

The local launchers and guides point to OpenClaw workflow scripts in that sibling folder.

## Main Features

- Background factor daemon for continuous local screening
- Multi-model aggregation across tree-based models
- Best-model selection report
- Candidate config generation and auto-backtest
- Promotion gate before updating the active Freqtrade auto config
- Telegram summary notifications
- Read-only dashboard for model and screening results

## Quick Start

Use the launchers in this folder:

- `OpenClaw Control Center.cmd`
- `Start OpenClaw Factor Daemon.cmd`
- `Launch Factor Dashboard.cmd`
- `Start Freqtrade Auto Bot.cmd`

## Important Files

- Guide: `OPENCLAW_FREQTRADE_GUIDE.md`
- Dashboard: `factor_lab.py`
- Main workflow: `../openclaw/scripts/freqtrade-daily-ml-screen.ps1`
- Auto bot config example: `user_data/config.openclaw-auto.example.json`
- Notification example: `openclaw.notification.example.json`

## Security

- Real API keys, bot tokens, chat ids, and local runtime configs are intentionally excluded from version control.
- Use the example config files and fill in your own local values after cloning.
