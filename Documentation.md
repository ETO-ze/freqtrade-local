# OpenClaw + Freqtrade Project Documentation Log

## 当前状态

- 项目根目录：`D:\Playground\freqtrade-local`
- 本地职责：行情缓存、动态山寨币池、因子训练、回测、promotion、运行时策略生成。
- 云端职责：运行 Freqtrade 实盘 Bot、接收已批准 active 配置、发布只读状态。
- 当前山寨策略：`AlternativeHunter`
- 当前 walk-forward 状态：已接入 stable 报告链路，当前为 `report-only`。
- 当前 Docker 训练限制：本机约 16GB 内存，Docker Desktop 当前约 7.43GiB 可用内存。

## 决策记录

- 本地模型训练保留长历史缓存，但训练阶段限制样本量，避免 Docker `exit code 137`。
- stable 默认模型组合优先保持稳定，不把高耗时模型无条件放入后台常规链路。
- walk-forward 先观察 2-3 轮 stable 结果，再决定是否升级为强制 promotion gate。
- 云端只运行通过审批的 active 配置，本地候选不直接覆盖实盘。
- 网站和 GUI 只展示状态，不暴露交易控制和敏感接口。

## 怎么运行

启动 GUI：

```powershell
cmd /c "D:\Playground\freqtrade-local\launchers\OpenClaw Control Center GUI.cmd"
```

启动本地因子看板：

```powershell
powershell -ExecutionPolicy Bypass -File D:\Playground\freqtrade-local\scripts\windows\start-factor-lab.ps1
```

启动 fast：

```powershell
powershell -ExecutionPolicy Bypass -File D:\Playground\freqtrade-local\scripts\windows\start-openclaw-factor-daemon-fast.ps1
```

启动 stable：

```powershell
powershell -ExecutionPolicy Bypass -File D:\Playground\freqtrade-local\scripts\windows\start-openclaw-factor-daemon-stable.ps1
```

停止 fast：

```powershell
powershell -ExecutionPolicy Bypass -File D:\Playground\freqtrade-local\scripts\windows\stop-openclaw-factor-daemon-fast.ps1
```

停止 stable：

```powershell
powershell -ExecutionPolicy Bypass -File D:\Playground\freqtrade-local\scripts\windows\stop-openclaw-factor-daemon-stable.ps1
```

手动运行 walk-forward：

```powershell
powershell -ExecutionPolicy Bypass -File D:\Playground\freqtrade-local\scripts\windows\run-walk-forward-retrain.ps1
```

发布网站看板数据：

```powershell
python D:\Playground\freqtrade-local\scripts\workflows\publish_dashboard_public_data.py
```

构建网站看板：

```powershell
cd D:\Playground\freqtrade-local\site\dashboard
cmd /c npm run build
```

安全同步 GitHub：

```powershell
powershell -ExecutionPolicy Bypass -File D:\Playground\freqtrade-local\scripts\windows\sync-github-safe.ps1
```

## 已知问题

- Docker Desktop 当前内存上限约 7.43GiB，复杂模型和全量长历史训练可能触发 `exit code 137`。
- walk-forward 当前为 report-only，不能视为已启用强制稳定性 gate。
- 本地报告、缓存、回测 zip、daemon logs 不应提交 GitHub。
- 如果 GUI 状态显示与实际进程不一致，优先检查 pid 文件、status JSON 和 Docker 临时容器。
- 如果网站看板没有最新数据，优先检查 `dashboard-data/backtest.json` 是否重新发布。

## 维护规则

- 每次修复后更新本文件的“当前状态”或“决策记录”。
- 每次新增启动脚本或入口后更新“怎么运行”。
- 每次发现稳定性问题后更新“已知问题”。
- 每次提交前检查 `git status --short`，确认没有误带 secrets、缓存、报告和数据。
