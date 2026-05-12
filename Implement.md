# Codex Implementation Guide

## 执行原则

- 按 `Plan.md` 的 milestone 顺序推进，不跳过验证。
- 每次只做当前任务需要的最小改动，diff 不要乱扩。
- 验证失败就修；不能修时记录原因、影响范围和下一步。
- 不覆盖用户已有改动，不执行 `git reset --hard`、`git checkout --` 等破坏性命令。
- 不自动提交 GitHub，除非用户明确要求。

## 安全边界

- 不读取、打印、提交真实 API key、secret、token、服务器密码。
- 不提交 `server.openclaw-sync.local.json`。
- 不提交 `user_data/data/`、`user_data/backtest_results/`、`reports/`、`dashboard-data/`、daemon logs、SQLite 数据库。
- 不随意重启云端 Freqtrade 实盘。
- 如果需要停止本地 Docker 或 WSL，先说明会影响哪些本地容器。

## 修改策略

- Python 脚本修改后运行 `python -m py_compile`。
- PowerShell 脚本修改后用 PowerShell Parser 做语法检查。
- Vue 看板修改后运行 `cmd /c npm run build`。
- GUI 修改后至少做 Python 编译检查，必要时启动 GUI 做人工观察。
- 训练链路修改后先跑小规模 Docker smoke test，再考虑重启后台 daemon。

## 失败处理

- `exit code 137`：优先判断 Docker/WSL 内存限制、训练样本量、模型复杂度和并发容器。
- `Unauthorized`：确认是否是受保护 API、Authenticator、token 或本机免 token 访问策略。
- GUI 卡死：优先检查同步命令是否阻塞主线程，长任务必须放后台线程。
- 看板无数据：先检查 `dashboard-data/*.json` 是否生成，再检查发布脚本和线上静态文件。
- promotion 未通过：先读审批报告，不直接放行，除非用户明确要走实验通道。

## 常用验证命令

```powershell
python -m py_compile D:\Playground\freqtrade-local\apps\desktop\control_center_gui.py
python -m py_compile D:\Playground\freqtrade-local\user_data\notebooks\train_alt_tree_models.py
python -m py_compile D:\Playground\freqtrade-local\scripts\workflows\publish_dashboard_public_data.py
```

```powershell
$tokens=$null; $errors=$null
[System.Management.Automation.Language.Parser]::ParseFile(
  "D:\Playground\freqtrade-local\scripts\windows\start-openclaw-factor-daemon-stable.ps1",
  [ref]$tokens,
  [ref]$errors
) | Out-Null
$errors
```

```powershell
cd D:\Playground\freqtrade-local\site\dashboard
cmd /c npm run build
```

```powershell
git status --short
git diff --stat
```

## Diff 控制

- 如果任务是文档，只改文档。
- 如果任务是 GUI，只改 GUI 和必要的数据读取接口。
- 如果任务是训练稳定性，只改训练脚本、daemon 参数和必要验证脚本。
- 如果发现无关脏文件，保留并在结果中说明，不回滚。
- 如果必须改外部 OpenClaw 脚本，明确说明该文件不属于当前 Git 仓库。
