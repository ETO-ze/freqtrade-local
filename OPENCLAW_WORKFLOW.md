# OpenClaw Freqtrade Workflow

Use OpenClaw as the outer control loop and keep the trade-time risk controls in Freqtrade.

Suggested split:

- `Freqtrade` handles signal generation, leverage caps, stoploss, and entry blocking.
- `OpenClaw` handles scheduled screening, backtests, report generation, and whitelist recommendations.

Current entry points:

- Strategy: `C:\Users\Administrator\Documents\Playground\freqtrade-local\user_data\strategies\BlitzkriegHunterAltV41.py`
- Config: `C:\Users\Administrator\Documents\Playground\freqtrade-local\user_data\config.backtest.okx-futures-alt-v41.json`
- OpenClaw helper: `C:\Users\Administrator\Documents\Playground\openclaw\scripts\freqtrade-alt-screen.ps1`
- Robust screener: `C:\Users\Administrator\Documents\Playground\openclaw\scripts\freqtrade-robust-screen.ps1`
- Daily ML screener: `C:\Users\Administrator\Documents\Playground\openclaw\scripts\freqtrade-daily-ml-screen.ps1`
- Telegram config: `C:\Users\Administrator\Documents\Playground\freqtrade-local\openclaw.notification.json`

Example local command:

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\Documents\Playground\openclaw\scripts\freqtrade-alt-screen.ps1
```

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\Documents\Playground\openclaw\scripts\freqtrade-robust-screen.ps1
```

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\Documents\Playground\openclaw\scripts\freqtrade-daily-ml-screen.ps1
```

Example OpenClaw prompt:

```text
Run the freqtrade alt screening workflow, summarize the newest backtest result, list the worst 5 and best 5 pairs, and recommend keep/remove candidates for tomorrow's dry-run whitelist.
```

```text
Run the robust alt screener across the configured time windows, rank pairs by stability, and propose keep/watch/drop buckets without changing live configs.
```

Recommended safe workflow:

1. OpenClaw runs the script on a schedule.
2. OpenClaw reads the newest result package, robust-screen JSON, and random-forest report.
3. OpenClaw proposes `tradable / observe / pause` buckets based on multi-window stability plus model edge.
4. OpenClaw posts the daily summary to Telegram if `openclaw.notification.json` is filled in.
5. You approve the changes before any dry-run or live config is updated.
