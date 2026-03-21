$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $root
$openClawScript = Join-Path $projectRoot 'openclaw\scripts\freqtrade-factor-daemon.ps1'
$daemonReportDir = Join-Path $root 'reports\daemon'
$logPath = Join-Path $daemonReportDir 'factor-daemon.log'
$pidPath = Join-Path $daemonReportDir 'factor-daemon.pid'

if (-not (Test-Path $daemonReportDir)) {
    New-Item -Path $daemonReportDir -ItemType Directory -Force | Out-Null
}

$existingLock = Join-Path $daemonReportDir 'factor-daemon.lock'
if (Test-Path $existingLock) {
    Write-Host "OpenClaw factor daemon appears to be running already. Lock: $existingLock" -ForegroundColor Yellow
    exit 0
}

$process = Start-Process powershell `
    -ArgumentList @(
        '-ExecutionPolicy', 'Bypass',
        '-File', $openClawScript,
        '-StateDir', $daemonReportDir,
        '-IntervalMinutes', '30'
    ) `
    -WorkingDirectory $projectRoot `
    -RedirectStandardOutput $logPath `
    -RedirectStandardError $logPath `
    -WindowStyle Hidden `
    -PassThru

Set-Content -Path $pidPath -Value $process.Id -Encoding ASCII
Write-Host "Started OpenClaw factor daemon in background. PID=$($process.Id)" -ForegroundColor Cyan
Write-Host "Log: $logPath" -ForegroundColor Cyan
