$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $root
$openClawScript = Join-Path $projectRoot 'openclaw\scripts\freqtrade-factor-daemon.ps1'
$daemonReportDir = Join-Path $root 'reports\daemon'
$stdoutPath = Join-Path $daemonReportDir 'factor-daemon-stable.out.log'
$stderrPath = Join-Path $daemonReportDir 'factor-daemon-stable.err.log'
$pidPath = Join-Path $daemonReportDir 'factor-daemon-stable.pid'

if (-not (Test-Path $daemonReportDir)) {
    New-Item -Path $daemonReportDir -ItemType Directory -Force | Out-Null
}

$existingLock = Join-Path $daemonReportDir 'factor-daemon-stable.lock'
if (Test-Path $existingLock) {
    Write-Host "OpenClaw stable daemon appears to be running already. Lock: $existingLock" -ForegroundColor Yellow
    exit 0
}

$process = Start-Process powershell `
    -ArgumentList @(
        '-ExecutionPolicy', 'Bypass',
        '-File', $openClawScript,
        '-StateDir', $daemonReportDir,
        '-IntervalMinutes', '180',
        '-DaemonName', 'factor-daemon-stable',
        '-WorkflowArguments', '-CandidateConfigPath|C:\Users\Administrator\Documents\Playground\freqtrade-local\user_data\config.backtest.okx-futures-alt-local-wide.json|-MlModels|tree,rf,hgb|-UseEvolution|0|-EvolutionOutputPrefix|/freqtrade/user_data/reports/ml/daily-alt-evolution-stable|-EvolutionPopulation|8|-EvolutionGenerations|3|-EvolutionElite|2|-EvolutionMutationRate|0.25|-AutoBacktestFreqtrade|1|-MlOutputPrefix|/freqtrade/user_data/reports/ml/daily-alt-tree-model-stable|-CombinedReportPath|C:\Users\Administrator\Documents\Playground\freqtrade-local\reports\openclaw-daily-alt-ml-stable.md|-CombinedJsonPath|C:\Users\Administrator\Documents\Playground\freqtrade-local\reports\openclaw-daily-alt-ml-stable.json|-StrategyUpdateReportPath|C:\Users\Administrator\Documents\Playground\freqtrade-local\reports\openclaw-strategy-update-stable.md|-BestModelJsonPath|C:\Users\Administrator\Documents\Playground\freqtrade-local\reports\openclaw-best-model-stable.json|-BestModelReportPath|C:\Users\Administrator\Documents\Playground\freqtrade-local\reports\openclaw-best-model-stable.md|-AutoBacktestReportPath|C:\Users\Administrator\Documents\Playground\freqtrade-local\reports\openclaw-auto-backtest-stable.md|-AutoBacktestJsonReportPath|C:\Users\Administrator\Documents\Playground\freqtrade-local\reports\openclaw-auto-backtest-stable.json|-ApprovalReportPath|C:\Users\Administrator\Documents\Playground\freqtrade-local\reports\openclaw-auto-approval-stable.md|-CandidateTargetConfigPath|C:\Users\Administrator\Documents\Playground\freqtrade-local\user_data\config.openclaw-candidate-stable.json|-UpdateLatestAliases|1'
    ) `
    -WorkingDirectory $projectRoot `
    -RedirectStandardOutput $stdoutPath `
    -RedirectStandardError $stderrPath `
    -WindowStyle Hidden `
    -PassThru

Set-Content -Path $pidPath -Value $process.Id -Encoding ASCII
Write-Host "Started OpenClaw stable factor daemon in background. PID=$($process.Id)" -ForegroundColor Cyan
Write-Host "Stdout: $stdoutPath" -ForegroundColor Cyan
Write-Host "Stderr: $stderrPath" -ForegroundColor Cyan
