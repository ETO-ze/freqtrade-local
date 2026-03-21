$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$reportRoot = Join-Path $root 'reports'
$daemonRoot = Join-Path $reportRoot 'daemon'
$statusPath = Join-Path $daemonRoot 'factor-daemon-status.json'
$logPath = Join-Path $daemonRoot 'factor-daemon.log'
$guidePath = Join-Path $root 'OPENCLAW_FREQTRADE_GUIDE.md'
$dashboardUrl = 'http://127.0.0.1:8501'
$botUrl = 'http://127.0.0.1:8081'

function Show-Header {
    Clear-Host
    Write-Host 'OpenClaw + Freqtrade Control Center' -ForegroundColor Cyan
    Write-Host ''
    if (Test-Path $statusPath) {
        try {
            $status = Get-Content $statusPath | ConvertFrom-Json
            Write-Host "Daemon status : $($status.status)" -ForegroundColor Green
            Write-Host "Last run      : $($status.started_at) -> $($status.completed_at)"
            Write-Host "Next run      : $($status.next_run_after)"
            Write-Host "Interval      : $($status.interval_minutes) minutes"
            if ($status.error) {
                Write-Host "Last error    : $($status.error)" -ForegroundColor Yellow
            }
        }
        catch {
            Write-Host 'Daemon status : unreadable status file' -ForegroundColor Yellow
        }
    }
    else {
        Write-Host 'Daemon status : not started yet' -ForegroundColor Yellow
    }
    Write-Host ''
}

function Pause-And-Return {
    Write-Host ''
    Read-Host 'Press Enter to return'
}

do {
    Show-Header
    Write-Host '1. Start factor daemon'
    Write-Host '2. Stop factor daemon'
    Write-Host '3. Start factor dashboard'
    Write-Host '4. Start Freqtrade auto bot'
    Write-Host '5. Open reports folder'
    Write-Host '6. Open daemon log'
    Write-Host '7. Open guide'
    Write-Host '8. Open dashboard in browser'
    Write-Host '9. Open Freqtrade bot API in browser'
    Write-Host '0. Exit'
    Write-Host ''

    $choice = Read-Host 'Select'
    switch ($choice) {
        '1' {
            powershell -ExecutionPolicy Bypass -File (Join-Path $root 'start-openclaw-factor-daemon.ps1')
            Pause-And-Return
        }
        '2' {
            powershell -ExecutionPolicy Bypass -File (Join-Path $root 'stop-openclaw-factor-daemon.ps1')
            Pause-And-Return
        }
        '3' {
            Start-Process powershell -ArgumentList @('-ExecutionPolicy', 'Bypass', '-File', (Join-Path $root 'start-factor-lab.ps1'))
        }
        '4' {
            powershell -ExecutionPolicy Bypass -File (Join-Path $root 'start-openclaw-auto-bot.ps1')
            Pause-And-Return
        }
        '5' {
            Start-Process explorer $reportRoot
        }
        '6' {
            if (Test-Path $logPath) {
                Start-Process notepad $logPath
            }
            else {
                Write-Host 'Log file not found yet.' -ForegroundColor Yellow
                Pause-And-Return
            }
        }
        '7' {
            Start-Process notepad $guidePath
        }
        '8' {
            Start-Process $dashboardUrl
        }
        '9' {
            Start-Process $botUrl
        }
        '0' {
            break
        }
        default {
            Write-Host 'Invalid selection.' -ForegroundColor Yellow
            Start-Sleep -Seconds 1
        }
    }
}
while ($true)
