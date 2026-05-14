$ErrorActionPreference = 'Stop'

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent (Split-Path -Parent $scriptRoot)
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

function Write-AtomicText {
    param(
        [string]$Path,
        [string]$Value,
        [string]$Encoding = 'UTF8'
    )
    $parent = Split-Path -Parent $Path
    if ($parent -and -not (Test-Path $parent)) {
        New-Item -Path $parent -ItemType Directory -Force | Out-Null
    }
    $tmp = "$Path.tmp"
    Set-Content -Path $tmp -Value $Value -Encoding $Encoding
    Move-Item -Path $tmp -Destination $Path -Force
}

function Write-AtomicJson {
    param(
        [string]$Path,
        [object]$Value
    )
    Write-AtomicText -Path $Path -Value ($Value | ConvertTo-Json -Depth 10) -Encoding UTF8
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
    Write-Host "OpenClaw autotune daemon process appears to be running already. PID: $($existingDaemon.ProcessId), status: $statusName" -ForegroundColor Yellow
    exit 0
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
        '-SharedRunLockName', 'openclaw-autotune-workflow.lock',
        '-WorkflowArguments', '-FreqtradeRoot|D:\Playground\freqtrade-local|-RuntimePolicyPath|D:\Playground\freqtrade-local\user_data\model_runtime_policy.json|-BaseConfigPath|D:\Playground\freqtrade-local\user_data\config.backtest.alternativehunter.json|-OutputJsonPath|D:\Playground\freqtrade-local\reports\openclaw-autotune-latest.json|-OutputReportPath|D:\Playground\freqtrade-local\reports\openclaw-autotune-latest.md|-ApprovedTuningPath|D:\Playground\freqtrade-local\user_data\model_runtime_tuning.auto.json|-StrategyName|AlternativeHunter|-Timerange|20251201-20260318|-TimerangeMode|start-floor|-TimerangeStartDateFloor|20250101|-Trials|16|-MaxPairs|14|-StakeAmount|50|-MaxOpenTrades|5|-MinAcceptedProfitPct|10|-MinAcceptedProfitFactor|1.5|-MinAcceptedWinratePct|60|-MaxAcceptedDrawdownPct|12|-MinAcceptedTrades|240'
    ) `
    -WorkingDirectory $projectRoot `
    -RedirectStandardOutput $stdoutPath `
    -RedirectStandardError $stderrPath `
    -WindowStyle Hidden `
    -PassThru

Write-AtomicText -Path $pidPath -Value $process.Id -Encoding ASCII
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
    Write-AtomicJson -Path $statusPath -Value $startingStatus
}
Write-Host "Started OpenClaw autotune daemon in background. PID=$($process.Id)" -ForegroundColor Cyan



