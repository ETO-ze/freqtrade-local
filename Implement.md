# Codex 执行指南

## 执行原则

- 按 `Plan.md` 的 milestone 推进，不跳过验证。
- 先备份、再修改；涉及配置、策略、GUI、同步脚本时尤其如此。
- 每次只做当前任务所需的最小修改，diff 不要扩散。
- 验证失败就修；不能修时记录原因、影响范围和下一步。
- 不回滚用户已有改动，不执行 `git reset --hard` 或 `git checkout --`。
- 不自动提交 GitHub，除非用户明确要求。

## 安全边界

- 不打印、不提交真实 API key、secret、token、服务器密码、交易所密钥。
- 不提交 `server.openclaw-sync.local.json`。
- 不提交 `reports/`、`dashboard-data/`、`user_data/backtest_cache/`、`user_data/backtest_results/`、行情数据、daemon logs、SQLite 数据库。
- 不随意重启云端实盘 Bot。
- 不在有持仓时直接强制切换策略；如需切换，必须先确认策略更新保护、持仓只读状态和云端重启逻辑。

## 本次任务执行范围

- 重写乱码协作文档：`Prompt.md`、`Plan.md`、`Implement.md`、`Documentation.md`。
- 新增项目框架和量化策略诊断文档：`docs/project/PROJECT_FRAMEWORK_AND_QUANT_REVIEW.md`。
- 执行非破坏验证：Python 编译、PowerShell 语法、Vue build、JSON 读取、服务器探测、Git 状态检查。
- 不修改交易策略、不修改 API、不重启云端实盘、不执行 promotion。

## 常用验证命令

Python 语法检查：

```powershell
python -m py_compile D:\Playground\freqtrade-local\apps\desktop\control_center_gui.py D:\Playground\freqtrade-local\apps\streamlit\factor_lab.py D:\Playground\freqtrade-local\scripts\workflows\publish_dashboard_public_data.py D:\Playground\freqtrade-local\scripts\workflows\run_walk_forward_retrain.py D:\Playground\freqtrade-local\user_data\notebooks\train_alt_tree_models.py D:\Playground\freqtrade-local\server\build_dashboard_status.py
```

PowerShell 语法检查：

```powershell
$files = @(
  "D:\Playground\freqtrade-local\scripts\windows\start-openclaw-factor-daemon-fast.ps1",
  "D:\Playground\freqtrade-local\scripts\windows\start-openclaw-factor-daemon-stable.ps1",
  "D:\Playground\freqtrade-local\scripts\windows\run-walk-forward-retrain.ps1",
  "D:\Playground\freqtrade-local\scripts\windows\sync-github-safe.ps1"
)
foreach ($file in $files) {
  $tokens=$null; $errors=$null
  [System.Management.Automation.Language.Parser]::ParseFile($file,[ref]$tokens,[ref]$errors) | Out-Null
  if ($errors.Count -gt 0) { $errors; exit 1 }
}
```

Vue dashboard 构建：

```powershell
cd D:\Playground\freqtrade-local\site\dashboard
cmd /c npm run build
```

JSON 读取检查：

```powershell
python - <<'PY'
import json
from pathlib import Path
root = Path(r"D:\Playground\freqtrade-local")
for rel in ["dashboard-data/backtest.json","reports/openclaw-daily-alt-ml-stable.json","reports/openclaw-approved-history.json"]:
    data = json.loads((root / rel).read_text(encoding="utf-8-sig"))
    print(rel, type(data).__name__)
PY
```

运行产物完整性检查：

```powershell
python D:\Playground\freqtrade-local\scripts\workflows\validate_openclaw_runtime_artifacts.py --required dashboard-data/backtest.json --required dashboard-data/alerts.json
```

服务器探测：

```powershell
python D:\Playground\freqtrade-local\scripts\workflows\probe_openclaw_server_status.py
```

Git 安全检查：

```powershell
git status --short
git diff --stat
```

## 失败处理

- `exit code 137`：优先检查 Docker/WSL 内存、并发容器、训练样本量、模型数量、缓存复用。
- GUI 卡死：检查是否把长命令放在主线程执行；长任务应后台线程执行并实时写状态。
- 看板无数据：先检查 `dashboard-data/backtest.json` 是否生成，再检查发布脚本和线上静态文件。
- `Unauthorized`：确认是 Authelia/Authenticator 保护、Freqtrade API 权限，还是本机免 token 配置失效。
- promotion 未通过：先读审批报告，不直接放行；除非用户明确要求走实验高风险通道。

## Diff 控制

- 文档任务只改文档。
- GUI 任务只改 GUI 和必要的数据读取接口。
- 训练任务只改训练脚本、daemon 参数和必要验证脚本。
- 网站任务只改 `site/` 与发布数据脚本。
- 如果发现无关脏文件，保留并在结果中说明，不回滚。
