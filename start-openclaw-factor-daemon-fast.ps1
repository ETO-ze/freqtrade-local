$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $root
$openClawScript = Join-Path $projectRoot 'openclaw\scripts\freqtrade-factor-daemon.ps1'
$daemonReportDir = Join-Path $root 'reports\daemon'
$stdoutPath = Join-Path $daemonReportDir 'factor-daemon-fast.out.log'
$stderrPath = Join-Path $daemonReportDir 'factor-daemon-fast.err.log'
$pidPath = Join-Path $daemonReportDir 'factor-daemon-fast.pid'

if (-not (Test-Path $daemonReportDir)) {
    New-Item -Path $daemonReportDir -ItemType Directory -Force | Out-Null
}

$existingLock = Join-Path $daemonReportDir 'factor-daemon-fast.lock'
if (Test-Path $existingLock) {
    Write-Host "OpenClaw fast daemon appears to be running already. Lock: $existingLock" -ForegroundColor Yellow
    exit 0
}

$process = Start-Process powershell `
    -ArgumentList @(
        '-ExecutionPolicy', 'Bypass',
        '-File', $openClawScript,
        '-StateDir', $daemonReportDir,
        '-IntervalMinutes', '20',
        '-StartupDelaySeconds', '45',
        '-DaemonName', 'factor-daemon-fast',
        '-WorkflowArguments', '-CandidateConfigPath|C:\Users\Administrator\Documents\Playground\freqtrade-local\user_data\config.backtest.okx-futures-alt-local-wide.json|-MlModels|rf|-AutoBacktestFreqtrade|0|-MlOutputPrefix|/freqtrade/user_data/reports/ml/daily-alt-tree-model-fast|-CombinedReportPath|C:\Users\Administrator\Documents\Playground\freqtrade-local\reports\openclaw-daily-alt-ml-fast.md|-CombinedJsonPath|C:\Users\Administrator\Documents\Playground\freqtrade-local\reports\openclaw-daily-alt-ml-fast.json|-StrategyUpdateReportPath|C:\Users\Administrator\Documents\Playground\freqtrade-local\reports\openclaw-strategy-update-fast.md|-BestModelJsonPath|C:\Users\Administrator\Documents\Playground\freqtrade-local\reports\openclaw-best-model-fast.json|-BestModelReportPath|C:\Users\Administrator\Documents\Playground\freqtrade-local\reports\openclaw-best-model-fast.md|-AutoBacktestReportPath|C:\Users\Administrator\Documents\Playground\freqtrade-local\reports\openclaw-auto-backtest-fast.md|-AutoBacktestJsonReportPath|C:\Users\Administrator\Documents\Playground\freqtrade-local\reports\openclaw-auto-backtest-fast.json|-ApprovalReportPath|C:\Users\Administrator\Documents\Playground\freqtrade-local\reports\openclaw-auto-approval-fast.md|-CandidateTargetConfigPath|C:\Users\Administrator\Documents\Playground\freqtrade-local\user_data\config.openclaw-candidate-fast.json|-UpdateLatestAliases|0'
    ) `
    -WorkingDirectory $projectRoot `
    -RedirectStandardOutput $stdoutPath `
    -RedirectStandardError $stderrPath `
    -WindowStyle Hidden `
    -PassThru

Set-Content -Path $pidPath -Value $process.Id -Encoding ASCII
Write-Host "Started OpenClaw fast factor daemon in background. PID=$($process.Id)" -ForegroundColor Cyan
Write-Host "Stdout: $stdoutPath" -ForegroundColor Cyan
Write-Host "Stderr: $stderrPath" -ForegroundColor Cyan
