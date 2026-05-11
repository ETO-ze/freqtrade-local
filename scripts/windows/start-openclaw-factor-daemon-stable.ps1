param(
    [int]$IntervalMinutes = 180,
    [int]$StartupDelaySeconds = 0,
    [switch]$ForceRestart
)

$ErrorActionPreference = 'Stop'

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent (Split-Path -Parent $scriptRoot)
$projectRoot = Split-Path -Parent $root
$openClawScript = Join-Path $projectRoot 'openclaw\scripts\freqtrade-factor-daemon.ps1'
$daemonReportDir = Join-Path $root 'reports\daemon'
$stdoutPath = Join-Path $daemonReportDir 'factor-daemon-stable.out.log'
$stderrPath = Join-Path $daemonReportDir 'factor-daemon-stable.err.log'
$pidPath = Join-Path $daemonReportDir 'factor-daemon-stable.pid'
$statusPath = Join-Path $daemonReportDir 'factor-daemon-stable-status.json'

if (-not (Test-Path $daemonReportDir)) {
    New-Item -Path $daemonReportDir -ItemType Directory -Force | Out-Null
}

$stopPath = Join-Path $daemonReportDir 'factor-daemon-stable.stop'
if (Test-Path $stopPath) {
    Remove-Item $stopPath -Force -ErrorAction SilentlyContinue
}

$statusData = $null
if (Test-Path $statusPath) {
    try {
        $statusData = Get-Content -Raw $statusPath | ConvertFrom-Json
    }
    catch {
        $statusData = $null
    }
}

$existingDaemon = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Name -eq 'powershell.exe' -and
        $_.CommandLine -match 'freqtrade-factor-daemon\.ps1' -and
        $_.CommandLine -match 'factor-daemon-stable'
    } |
    Select-Object -First 1

if ($existingDaemon) {
    $statusName = if ($statusData) { [string]$statusData.status } else { '' }
    if ($statusName -in @('running', 'starting') -and -not $ForceRestart.IsPresent) {
        Write-Host "OpenClaw stable daemon process appears to be running already. PID: $($existingDaemon.ProcessId)" -ForegroundColor Yellow
        exit 0
    }
    try {
        Stop-Process -Id $existingDaemon.ProcessId -Force -ErrorAction Stop
        Write-Host "Removed stale stable daemon PID: $($existingDaemon.ProcessId)" -ForegroundColor Yellow
    }
    catch {
        Write-Host "Failed to remove stale stable daemon PID $($existingDaemon.ProcessId): $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

$existingLock = Join-Path $daemonReportDir 'factor-daemon-stable.lock'
$existingPid = $null
if (Test-Path $pidPath) {
    try {
        $existingPid = [int](Get-Content $pidPath -ErrorAction Stop | Select-Object -First 1)
    }
    catch {
        $existingPid = $null
    }
}

if ($existingPid) {
    $pidProcess = Get-Process -Id $existingPid -ErrorAction SilentlyContinue
    if ($pidProcess) {
        $statusName = if ($statusData) { [string]$statusData.status } else { '' }
        if ($statusName -in @('running', 'starting') -and -not $ForceRestart.IsPresent) {
            Write-Host "OpenClaw stable daemon PID file points to a live process already. PID: $existingPid" -ForegroundColor Yellow
            exit 0
        }
        try {
            Stop-Process -Id $existingPid -Force -ErrorAction Stop
            Write-Host "Removed stale stable PID from PID file: $existingPid" -ForegroundColor Yellow
        }
        catch {
            Write-Host ("Failed to remove stale stable PID {0}: {1}" -f $existingPid, $_.Exception.Message) -ForegroundColor Yellow
        }
    }
}

if (Test-Path $existingLock) {
    Remove-Item $existingLock -Force -ErrorAction SilentlyContinue
}

if (Test-Path $pidPath) {
    Remove-Item $pidPath -Force -ErrorAction SilentlyContinue
}

$process = Start-Process powershell `
    -ArgumentList @(
        '-ExecutionPolicy', 'Bypass',
        '-File', $openClawScript,
        '-StateDir', $daemonReportDir,
        '-IntervalMinutes', "$IntervalMinutes",
        '-StartupDelaySeconds', "$StartupDelaySeconds",
        '-DaemonName', 'factor-daemon-stable',
        '-SharedRunLockName', 'openclaw-ml-training.lock',
        '-WorkflowArguments', '-CandidateConfigPath|D:\Playground\freqtrade-local\user_data\config.backtest.okx-futures-alt-local-wide.json|-MarketDataRefreshEnabled|1|-MarketDataRefreshScriptPath|D:\Playground\freqtrade-local\scripts\windows\refresh_alt_market_data.ps1|-MarketDataRefreshDays|7|-DynamicUniverseEnabled|1|-DynamicUniverseScriptPath|D:\Playground\freqtrade-local\scripts\workflows\build_dynamic_alt_universe.py|-DynamicUniverseOutputConfigPath|D:\Playground\freqtrade-local\user_data\config.backtest.okx-futures-alt-local-dynamic.generated.json|-DynamicUniverseReportPath|D:\Playground\freqtrade-local\reports\openclaw-dynamic-alt-universe.md|-DynamicUniverseJsonPath|D:\Playground\freqtrade-local\reports\openclaw-dynamic-alt-universe.json|-DynamicUniverseTopN|15|-DynamicUniverseMinHistoryDays|30|-DynamicUniverseMarketCapSource|coingecko|-DynamicUniverseMarketCapTopN|500|-DynamicUniverseMarketCapPages|2|-DynamicUniverseMinMarketCapUsd|30000000|-DynamicUniverseMinMarketVolumeUsd|300000|-DynamicUniverseMaxVolumeToMarketCapRatio|3.5|-DynamicUniverseRequireMarketCap|1|-MlModels|tree,rf,hgb,xgb|-MlDockerImage|freqtrade-local-ml-gpu:latest|-UseGpuForMl|1|-UseEvolution|0|-RobustScreenCacheTtlMinutes|180|-EvolutionOutputPrefix|/freqtrade/user_data/reports/ml/daily-alt-evolution-stable|-EvolutionPopulation|8|-EvolutionGenerations|3|-EvolutionElite|2|-EvolutionMutationRate|0.25|-AutoSyncMaxPairs|10|-AutoBacktestFreqtrade|1|-AutoBacktestTimerangeMode|auto|-AutoBacktestStartDateFloor|20250101|-AutoBacktestLookbackDays|520|-ExperimentalHighProfitBypass|1|-ExperimentalHighProfitPct|80|-ExperimentalMinProfitFactor|1.3|-ExperimentalMaxDrawdownPct|30|-ExperimentalMinWinratePct|60|-ExperimentalMinTrades|300|-BacktestStabilityGate|1|-BacktestStabilityScriptPath|D:\Playground\freqtrade-local\scripts\workflows\evaluate_backtest_stability.py|-BacktestStabilityReportPath|D:\Playground\freqtrade-local\reports\openclaw-backtest-stability-stable.md|-BacktestStabilityJsonPath|D:\Playground\freqtrade-local\reports\openclaw-backtest-stability-stable.json|-MlOutputPrefix|/freqtrade/user_data/reports/ml/daily-alt-tree-model-stable|-CombinedReportPath|D:\Playground\freqtrade-local\reports\openclaw-daily-alt-ml-stable.md|-CombinedJsonPath|D:\Playground\freqtrade-local\reports\openclaw-daily-alt-ml-stable.json|-StrategyUpdateReportPath|D:\Playground\freqtrade-local\reports\openclaw-strategy-update-stable.md|-BestModelJsonPath|D:\Playground\freqtrade-local\reports\openclaw-best-model-stable.json|-BestModelReportPath|D:\Playground\freqtrade-local\reports\openclaw-best-model-stable.md|-AutoBacktestReportPath|D:\Playground\freqtrade-local\reports\openclaw-auto-backtest-stable.md|-AutoBacktestJsonReportPath|D:\Playground\freqtrade-local\reports\openclaw-auto-backtest-stable.json|-ApprovalReportPath|D:\Playground\freqtrade-local\reports\openclaw-auto-approval-stable.md|-CandidateTargetConfigPath|D:\Playground\freqtrade-local\user_data\config.openclaw-candidate-stable.json|-UpdateLatestAliases|1|-RemoteSyncServer|1|-RemoteSyncSettingsPath|D:\Playground\freqtrade-local\server.openclaw-sync.local.json|-RemoteSyncRestartBot|always|-PublishDashboardPublicData|1|-DashboardPublicPublishScriptPath|D:\Playground\freqtrade-local\scripts\workflows\publish_dashboard_public_data.py'
    ) `
    -WorkingDirectory $projectRoot `
    -RedirectStandardOutput $stdoutPath `
    -RedirectStandardError $stderrPath `
    -WindowStyle Hidden `
    -PassThru

Set-Content -Path $pidPath -Value $process.Id -Encoding ASCII
$now = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
Start-Sleep -Milliseconds 300
$currentStatus = $null
if (Test-Path $statusPath) {
    try {
        $currentStatus = Get-Content -Raw $statusPath | ConvertFrom-Json
    }
    catch {
        $currentStatus = $null
    }
}
if (-not $currentStatus -or [int]$currentStatus.pid -ne $process.Id -or [string]$currentStatus.status -eq 'stopped') {
    $startingStatus = [ordered]@{
        pid                   = $process.Id
        run                   = 0
        started_at            = $now
        completed_at          = $null
        status                = 'starting'
        interval_minutes      = $IntervalMinutes
        startup_delay_seconds = $StartupDelaySeconds
        workflow_script       = $openClawScript
        daemon_name           = 'factor-daemon-stable'
        next_run_after        = $null
        error                 = $null
    }
    $startingStatus | ConvertTo-Json -Depth 10 | Set-Content -Path $statusPath -Encoding UTF8
}
Write-Host "Started OpenClaw stable factor daemon in background. PID=$($process.Id)" -ForegroundColor Cyan
Write-Host "Stdout: $stdoutPath" -ForegroundColor Cyan
Write-Host "Stderr: $stderrPath" -ForegroundColor Cyan



