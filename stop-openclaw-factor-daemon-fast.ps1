$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$daemonReportDir = Join-Path $root 'reports\daemon'
$stopPath = Join-Path $daemonReportDir 'factor-daemon-fast.stop'
$pidPath = Join-Path $daemonReportDir 'factor-daemon-fast.pid'

if (-not (Test-Path $daemonReportDir)) {
    Write-Host 'Daemon state directory does not exist.' -ForegroundColor Yellow
    exit 0
}

Set-Content -Path $stopPath -Value 'stop' -Encoding ASCII
Write-Host "Stop signal written: $stopPath" -ForegroundColor Cyan

if (Test-Path $pidPath) {
    $pidValue = Get-Content $pidPath -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($pidValue) {
        Write-Host "Daemon PID: $pidValue" -ForegroundColor Cyan
    }
}
