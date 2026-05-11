# Project Overview

## What This Project Is

This project combines local model research with server-side Freqtrade execution.

- Local machine: data refresh, dynamic-universe building, screening, model training, candidate backtests, approval.
- Server: bot runtime, protected UI, HTTPS access, and public read-only dashboard data.

## Core Components

### OpenClaw research loop
- Refresh OKX futures market data
- Build a dynamic altcoin universe from liquidity and stability proxies
- Run robust screen
- Train tree-based models
- Generate tradable / observe / pause decisions
- Backtest candidate configs
- Promote only if the gate is passed

### Freqtrade runtime
- Altcoin execution lane
- Mainstream execution lane
- HTTPS protected web UI
- API endpoint for clients

## Current Design Choices

### Dynamic universes
- `stable` uses a narrower dynamic universe (`top_n = 15`)
- `fast` uses a wider dynamic universe (`top_n = 20`)

This split exists because the formal lane should optimize for quality, while the lightweight lane should optimize for coverage and early observation.

### Approval gate
Promotion is intentionally strict.

- Profit must be high enough
- Drawdown must stay contained
- Trade count must be sufficient
- A high-profit bypass exists, but it is still conservative

## Current Constraint

The pipeline is now structurally sound, but current post-refresh results do not yet pass the stable promotion gate.

That means:
- the automation is working correctly
- the server runtime is protected from weak candidate updates
- the next optimization target is factor quality, not workflow plumbing

## Next Optimization Priorities

1. Reduce `mark_premium` family dominance in model selection
2. Improve orthogonal signal contribution
3. Add stricter noise filtering to dynamic-universe expansion
4. Keep promotion strict while widening only the research universe
