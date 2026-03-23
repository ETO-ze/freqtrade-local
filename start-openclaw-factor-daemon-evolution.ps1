$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $root
$openClawScript = Join-Path $projectRoot 'openclaw\scripts\freqtrade-factor-daemon.ps1'
$daemonReportDir = Join-Path $root 'reports\daemon'
$stdoutPath = Join-Path $daemonReportDir 'factor-daemon-evolution.out.log'
$stderrPath = Join-Path $daemonReportDir 'factor-daemon-evolution.err.log'
$pidPath = Join-Path $daemonReportDir 'factor-daemon-evolution.pid'

if (-not (Test-Path $daemonReportDir)) {
    New-Item -Path $daemonReportDir -ItemType Directory -Force | Out-Null
}

$existingLock = Join-Path $daemonReportDir 'factor-daemon-evolution.lock'
if (Test-Path $existingLock) {
    Write-Host "OpenClaw evolution daemon appears to be running already. Lock: $existingLock" -ForegroundColor Yellow
    exit 0
}

$process = Start-Process powershell `
    -ArgumentList @(
        '-ExecutionPolicy', 'Bypass',
        '-File', $openClawScript,
        '-StateDir', $daemonReportDir,
        '-IntervalMinutes', '720',
        '-StartupDelaySeconds', '15',
        '-DaemonName', 'factor-daemon-evolution',
        '-WorkflowArguments', '-CandidateConfigPath|C:\Users\Administrator\Documents\Playground\freqtrade-local\user_data\config.backtest.okx-futures-alt-local-wide.json|-MlModels|tree,rf,hgb|-UseEvolution|1|-EvolutionOutputPrefix|/freqtrade/user_data/reports/ml/daily-alt-evolution-research|-EvolutionPopulation|8|-EvolutionGenerations|3|-EvolutionElite|2|-EvolutionMutationRate|0.25|-AutoSyncFreqtrade|0|-AutoBacktestFreqtrade|0|-MlOutputPrefix|/freqtrade/user_data/reports/ml/daily-alt-tree-model-evolution|-CombinedReportPath|C:\Users\Administrator\Documents\Playground\freqtrade-local\reports\openclaw-daily-alt-ml-evolution.md|-CombinedJsonPath|C:\Users\Administrator\Documents\Playground\freqtrade-local\reports\openclaw-daily-alt-ml-evolution.json|-StrategyUpdateReportPath|C:\Users\Administrator\Documents\Playground\freqtrade-local\reports\openclaw-strategy-update-evolution.md|-BestModelJsonPath|C:\Users\Administrator\Documents\Playground\freqtrade-local\reports\openclaw-best-model-evolution.json|-BestModelReportPath|C:\Users\Administrator\Documents\Playground\freqtrade-local\reports\openclaw-best-model-evolution.md|-AutoBacktestReportPath|C:\Users\Administrator\Documents\Playground\freqtrade-local\reports\openclaw-auto-backtest-evolution.md|-AutoBacktestJsonReportPath|C:\Users\Administrator\Documents\Playground\freqtrade-local\reports\openclaw-auto-backtest-evolution.json|-ApprovalReportPath|C:\Users\Administrator\Documents\Playground\freqtrade-local\reports\openclaw-auto-approval-evolution.md|-CandidateTargetConfigPath|C:\Users\Administrator\Documents\Playground\freqtrade-local\user_data\config.openclaw-candidate-evolution.json|-UpdateLatestAliases|0'
    ) `
    -WorkingDirectory $projectRoot `
    -RedirectStandardOutput $stdoutPath `
    -RedirectStandardError $stderrPath `
    -WindowStyle Hidden `
    -PassThru

Set-Content -Path $pidPath -Value $process.Id -Encoding ASCII
Write-Host "Started OpenClaw evolution daemon in background. PID=$($process.Id)" -ForegroundColor Cyan
Write-Host "Stdout: $stdoutPath" -ForegroundColor Cyan
Write-Host "Stderr: $stderrPath" -ForegroundColor Cyan
