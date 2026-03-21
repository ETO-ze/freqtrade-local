# OpenClaw Auto Sync

This workflow lets OpenClaw train and screen altcoin factors locally, backtest the candidate set, and only promote it into a dedicated Freqtrade dry-run config when the backtest passes the configured gates.

Files:

- `C:\Users\Administrator\Documents\Playground\openclaw\scripts\freqtrade-sync-screen-to-config.ps1`
- `C:\Users\Administrator\Documents\Playground\openclaw\scripts\freqtrade-backtest-openclaw-auto.ps1`
- `C:\Users\Administrator\Documents\Playground\freqtrade-local\user_data\config.openclaw-auto.json`
- `C:\Users\Administrator\Documents\Playground\freqtrade-local\start-openclaw-auto-bot.ps1`

Safe default behavior:

- updates only `config.openclaw-auto.json`
- does not touch the existing `config.json`
- uses `dry_run = true`
- uses `max_open_trades = 5`
- starts a separate bot on port `8081`
- builds a candidate config first
- runs a local backtest after each factor screen
- promotes the candidate only when the backtest meets the configured thresholds

Run screening + sync:

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\Documents\Playground\openclaw\scripts\freqtrade-daily-ml-screen.ps1
powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\Documents\Playground\openclaw\scripts\freqtrade-sync-screen-to-config.ps1
```

Approval reports:

- `C:\Users\Administrator\Documents\Playground\freqtrade-local\reports\openclaw-auto-approval-latest.md`
- `C:\Users\Administrator\Documents\Playground\freqtrade-local\reports\openclaw-auto-backtest-latest.json`

Run the generated auto-config backtest only:

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\Documents\Playground\openclaw\scripts\freqtrade-backtest-openclaw-auto.ps1
```

Start the separate bot:

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\Documents\Playground\freqtrade-local\start-openclaw-auto-bot.ps1
```
