$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $root
$openClawScript = Join-Path $projectRoot 'openclaw\scripts\freqtrade-factor-daemon.ps1'
$daemonReportDir = Join-Path $root 'reports\daemon'
$stdoutPath = Join-Path $daemonReportDir 'factor-daemon-fast.out.log'
$stderrPath = Join-Path $daemonReportDir 'factor-daemon-fast.err.log'
$pidPath = Join-Path $daemonReportDir 'factor-daemon-fast.pid'
$statusPath = Join-Path $daemonReportDir 'factor-daemon-fast-status.json'

if (-not (Test-Path $daemonReportDir)) {
    New-Item -Path $daemonReportDir -ItemType Directory -Force | Out-Null
}

$stopPath = Join-Path $daemonReportDir 'factor-daemon-fast.stop'
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
        $_.CommandLine -match 'factor-daemon-fast'
    } |
    Select-Object -First 1

if ($existingDaemon) {
    $statusName = if ($statusData) { [string]$statusData.status } else { '' }
    if ($statusName -in @('running', 'starting')) {
        Write-Host "OpenClaw fast daemon process appears to be running already. PID: $($existingDaemon.ProcessId)" -ForegroundColor Yellow
        exit 0
    }
    try {
        Stop-Process -Id $existingDaemon.ProcessId -Force -ErrorAction Stop
        Write-Host "Removed stale fast daemon PID: $($existingDaemon.ProcessId)" -ForegroundColor Yellow
    }
    catch {
        Write-Host "Failed to remove stale fast daemon PID $($existingDaemon.ProcessId): $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

$existingLock = Join-Path $daemonReportDir 'factor-daemon-fast.lock'
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
        if ($statusName -in @('running', 'starting')) {
            Write-Host "OpenClaw fast daemon PID file points to a live process already. PID: $existingPid" -ForegroundColor Yellow
            exit 0
        }
        try {
            Stop-Process -Id $existingPid -Force -ErrorAction Stop
            Write-Host "Removed stale fast PID from PID file: $existingPid" -ForegroundColor Yellow
        }
        catch {
            Write-Host ("Failed to remove stale fast PID {0}: {1}" -f $existingPid, $_.Exception.Message) -ForegroundColor Yellow
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
        interval_minutes      = 20
        startup_delay_seconds = 45
        workflow_script       = $openClawScript
        daemon_name           = 'factor-daemon-fast'
        next_run_after        = $null
        error                 = $null
    }
    $startingStatus | ConvertTo-Json -Depth 10 | Set-Content -Path $statusPath -Encoding UTF8
}
Write-Host "Started OpenClaw fast factor daemon in background. PID=$($process.Id)" -ForegroundColor Cyan
Write-Host "Stdout: $stdoutPath" -ForegroundColor Cyan
Write-Host "Stderr: $stderrPath" -ForegroundColor Cyan
