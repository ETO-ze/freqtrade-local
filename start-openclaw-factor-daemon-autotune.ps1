$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $root
$openClawScript = Join-Path $projectRoot 'openclaw\scripts\freqtrade-factor-daemon.ps1'
$workflowScript = Join-Path $projectRoot 'openclaw\scripts\freqtrade-auto-tune-alternativehunter.ps1'
$daemonReportDir = Join-Path $root 'reports\daemon'
$stdoutPath = Join-Path $daemonReportDir 'factor-daemon-autotune.out.log'
$stderrPath = Join-Path $daemonReportDir 'factor-daemon-autotune.err.log'
$pidPath = Join-Path $daemonReportDir 'factor-daemon-autotune.pid'
$statusPath = Join-Path $daemonReportDir 'factor-daemon-autotune-status.json'

if (-not (Test-Path $daemonReportDir)) {
    New-Item -Path $daemonReportDir -ItemType Directory -Force | Out-Null
}

$stopPath = Join-Path $daemonReportDir 'factor-daemon-autotune.stop'
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
        $_.CommandLine -match 'factor-daemon-autotune'
    } |
    Select-Object -First 1

if ($existingDaemon) {
    $statusName = if ($statusData) { [string]$statusData.status } else { '' }
    if ($statusName -in @('running', 'starting')) {
        Write-Host "OpenClaw autotune daemon process appears to be running already. PID: $($existingDaemon.ProcessId)" -ForegroundColor Yellow
        exit 0
    }
    try {
        Stop-Process -Id $existingDaemon.ProcessId -Force -ErrorAction Stop
        Write-Host "Removed stale autotune daemon PID: $($existingDaemon.ProcessId)" -ForegroundColor Yellow
    }
    catch {
        Write-Host "Failed to remove stale autotune daemon PID $($existingDaemon.ProcessId): $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

$existingLock = Join-Path $daemonReportDir 'factor-daemon-autotune.lock'
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
        '-WorkflowScriptPath', $workflowScript,
        '-StateDir', $daemonReportDir,
        '-IntervalMinutes', '720',
        '-StartupDelaySeconds', '60',
        '-DaemonName', 'factor-daemon-autotune',
        '-WorkflowArguments', '-FreqtradeRoot|C:\Users\Administrator\Documents\Playground\freqtrade-local|-RuntimePolicyPath|C:\Users\Administrator\Documents\Playground\freqtrade-local\user_data\model_runtime_policy.json|-BaseConfigPath|C:\Users\Administrator\Documents\Playground\freqtrade-local\user_data\config.backtest.alternativehunter.json|-OutputJsonPath|C:\Users\Administrator\Documents\Playground\freqtrade-local\reports\openclaw-autotune-latest.json|-OutputReportPath|C:\Users\Administrator\Documents\Playground\freqtrade-local\reports\openclaw-autotune-latest.md|-ApprovedTuningPath|C:\Users\Administrator\Documents\Playground\freqtrade-local\user_data\model_runtime_tuning.auto.json|-StrategyName|AlternativeHunter|-Timerange|20251201-20260318|-Trials|16|-MaxPairs|14|-StakeAmount|50|-MaxOpenTrades|5|-MinAcceptedProfitPct|10|-MinAcceptedProfitFactor|1.5|-MinAcceptedWinratePct|60|-MaxAcceptedDrawdownPct|12|-MinAcceptedTrades|240'
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
        interval_minutes      = 720
        startup_delay_seconds = 60
        workflow_script       = $workflowScript
        daemon_name           = 'factor-daemon-autotune'
        next_run_after        = $null
        error                 = $null
    }
    $startingStatus | ConvertTo-Json -Depth 10 | Set-Content -Path $statusPath -Encoding UTF8
}
Write-Host "Started OpenClaw autotune daemon in background. PID=$($process.Id)" -ForegroundColor Cyan
