# OpenClaw + Freqtrade Open Task Plan

## Milestone 1: 稳定本地后台训练

目标：确保 `fast`、`stable`、`autotune`、手动 `evolution` 的启动、停止、状态展示稳定。

Acceptance Criteria:

- `fast` 和 `stable` 可通过 GUI 或 PowerShell 启动。
- 后台状态文件能正确显示 `starting`、`running`、`waiting`、`ok`、`error`。
- 本地模型训练不再因常规币池触发 Docker `exit code 137`。
- 停止后台任务时能清理临时训练容器和 stale pid。

Validation Commands:

```powershell
powershell -ExecutionPolicy Bypass -File D:\Playground\freqtrade-local\scripts\windows\start-openclaw-factor-daemon-fast.ps1
powershell -ExecutionPolicy Bypass -File D:\Playground\freqtrade-local\scripts\windows\start-openclaw-factor-daemon-stable.ps1
Get-Content D:\Playground\freqtrade-local\reports\daemon\factor-daemon-fast-status.json
Get-Content D:\Playground\freqtrade-local\reports\daemon\factor-daemon-stable-status.json
docker ps --format "table {{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Image}}"
```

## Milestone 2: 完善 promotion 与 active 因子保护

目标：候选因子只有在明显优于当前 active 或通过既定比较规则时才更新。

Acceptance Criteria:

- 未达标候选不会覆盖当前 active 配置。
- 已批准因子历史可在本地看板和网站看板展示。
- 高收益高风险通道只作为明确的实验放行逻辑，不隐藏风险指标。
- 云端只接收已批准 active 配置。

Validation Commands:

```powershell
Get-Content D:\Playground\freqtrade-local\reports\openclaw-auto-approval-stable.md
Get-Content D:\Playground\freqtrade-local\reports\openclaw-approved-history.json
Get-Content D:\Playground\freqtrade-local\user_data\model_runtime_policy.json
```

## Milestone 3: 接入并观察 Walk-forward 重训

目标：把独立窗口重训作为稳定性观察工具，先保持 report-only。

Acceptance Criteria:

- `run_walk_forward_retrain.py` 能生成 JSON 和 Markdown 报告。
- stable 后台能自动触发 walk-forward report-only。
- GUI 和网站看板能展示窗口通过数、评分、共识模型和 hard blocks。
- 未经确认前不把 `WalkForwardRetrainGate` 改成强制 gate。

Validation Commands:

```powershell
powershell -ExecutionPolicy Bypass -File D:\Playground\freqtrade-local\scripts\windows\run-walk-forward-retrain.ps1 -DryRun
Test-Path D:\Playground\freqtrade-local\reports\openclaw-walk-forward-retrain-stable.json
Select-String -Path D:\Playground\freqtrade-local\reports\openclaw-walk-forward-retrain-stable.md -Pattern "OpenClaw Walk-Forward Retrain"
```

## Milestone 4: 保持网站与 GUI 同步

目标：本地 GUI、Streamlit 看板、Vue 网站看板显示同一套关键状态。

Acceptance Criteria:

- GUI 能显示 active 因子、本地后台、服务器同步、walk-forward 状态。
- 网站 `/dashboard/backtest` 能显示 active 回测、已批准历史、walk-forward、实盘只读摘要。
- `publish_dashboard_public_data.py` 能生成并上传 `backtest.json` 和 `alerts.json`。
- 前端 build 通过。

Validation Commands:

```powershell
python -m py_compile D:\Playground\freqtrade-local\apps\desktop\control_center_gui.py
python -m py_compile D:\Playground\freqtrade-local\scripts\workflows\publish_dashboard_public_data.py
cd D:\Playground\freqtrade-local\site\dashboard
cmd /c npm run build
```

## Milestone 5: 安全同步 GitHub

目标：只提交可公开展示的代码、文档、脚本和静态资源。

Acceptance Criteria:

- 不提交本地密钥、服务器同步配置、API 配置、行情缓存、回测结果、日志。
- README 和协作文档能反映当前项目能力。
- Git diff 范围与本次任务一致。

Validation Commands:

```powershell
git status --short
git diff --stat
powershell -ExecutionPolicy Bypass -File D:\Playground\freqtrade-local\scripts\windows\sync-github-safe.ps1
```
