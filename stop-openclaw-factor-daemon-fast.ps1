$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$daemonReportDir = Join-Path $root 'reports\daemon'
$stopPath = Join-Path $daemonReportDir 'factor-daemon-fast.stop'
$pidPath = Join-Path $daemonReportDir 'factor-daemon-fast.pid'
$lockPath = Join-Path $daemonReportDir 'factor-daemon-fast.lock'
$statusPath = Join-Path $daemonReportDir 'factor-daemon-fast-status.json'

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

$matchingDaemons = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Name -eq 'powershell.exe' -and
        $_.CommandLine -match 'freqtrade-factor-daemon\.ps1' -and
        $_.CommandLine -match 'factor-daemon-fast'
    }

foreach ($daemon in $matchingDaemons) {
    try {
        Stop-Process -Id $daemon.ProcessId -Force -ErrorAction Stop
        Write-Host "Stopped fast daemon PID: $($daemon.ProcessId)" -ForegroundColor Cyan
    }
    catch {
        Write-Host "Failed to stop fast daemon PID $($daemon.ProcessId): $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

foreach ($path in @($pidPath, $lockPath)) {
    if (Test-Path $path) {
        Remove-Item $path -Force -ErrorAction SilentlyContinue
    }
}

if (Test-Path $statusPath) {
    try {
        $status = Get-Content -Raw $statusPath | ConvertFrom-Json
    }
    catch {
        $status = [pscustomobject]@{}
    }
}
else {
    $status = [pscustomobject]@{}
}

$now = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
$status | Add-Member -NotePropertyName completed_at -NotePropertyValue $now -Force
$status | Add-Member -NotePropertyName status -NotePropertyValue 'stopped' -Force
$status | Add-Member -NotePropertyName next_run_after -NotePropertyValue $null -Force
$status | Add-Member -NotePropertyName error -NotePropertyValue 'Stopped by user.' -Force
$status | ConvertTo-Json -Depth 10 | Set-Content -Path $statusPath -Encoding UTF8
