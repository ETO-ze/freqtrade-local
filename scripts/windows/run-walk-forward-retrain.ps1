param(
    [string]$ProjectRoot = "D:\Playground\freqtrade-local",
    [string]$ConfigPath = "",
    [string]$OutputJson = "",
    [string]$OutputMarkdown = "",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

if (-not $ConfigPath) {
    $ConfigPath = Join-Path $ProjectRoot "user_data\config.backtest.okx-futures-alt-local-dynamic.generated.json"
}
if (-not $OutputJson) {
    $OutputJson = Join-Path $ProjectRoot "reports\openclaw-walk-forward-retrain-stable.json"
}
if (-not $OutputMarkdown) {
    $OutputMarkdown = Join-Path $ProjectRoot "reports\openclaw-walk-forward-retrain-stable.md"
}

$scriptPath = Join-Path $ProjectRoot "scripts\workflows\run_walk_forward_retrain.py"
$args = @(
    $scriptPath,
    "--project-root", $ProjectRoot,
    "--config-path", $ConfigPath,
    "--output-json", $OutputJson,
    "--output-md", $OutputMarkdown
)

if ($DryRun) {
    $args += "--dry-run"
}

python @args
