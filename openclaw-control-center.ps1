$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$reportRoot = Join-Path $root 'reports'
$daemonRoot = Join-Path $reportRoot 'daemon'
$fastStatusPath = Join-Path $daemonRoot 'factor-daemon-fast-status.json'
$stableStatusPath = Join-Path $daemonRoot 'factor-daemon-stable-status.json'
$fastLogPath = Join-Path $daemonRoot 'factor-daemon-fast.out.log'
$stableLogPath = Join-Path $daemonRoot 'factor-daemon-stable.out.log'
$guidePath = Join-Path $root 'OPENCLAW_FREQTRADE_GUIDE.md'
$dashboardUrl = 'http://127.0.0.1:8501'
$botUrl = 'http://127.0.0.1:8081'

function Show-DaemonStatus([string]$Label, [string]$Path) {
    if (Test-Path $Path) {
        try {
            $status = Get-Content $Path | ConvertFrom-Json
            Write-Host "$Label : $($status.status)" -ForegroundColor Green
            Write-Host "Started    : $($status.started_at)"
            Write-Host "Completed  : $($status.completed_at)"
            Write-Host "Next run   : $($status.next_run_after)"
            if ($status.error) {
                Write-Host "Last error : $($status.error)" -ForegroundColor Yellow
            }
        }
        catch {
            Write-Host "$Label : unreadable status file" -ForegroundColor Yellow
        }
    }
    else {
        Write-Host "$Label : not started yet" -ForegroundColor Yellow
    }
    Write-Host ''
}

function Show-Header {
    Clear-Host
    Write-Host 'OpenClaw + Freqtrade Control Center' -ForegroundColor Cyan
    Write-Host ''
    Show-DaemonStatus 'Fast daemon' $fastStatusPath
    Show-DaemonStatus 'Stable daemon' $stableStatusPath
}

function Pause-And-Return {
    Write-Host ''
    Read-Host 'Press Enter to return'
}

do {
    Show-Header
    Write-Host '1. Start fast daemon'
    Write-Host '2. Stop fast daemon'
    Write-Host '3. Start stable daemon'
    Write-Host '4. Stop stable daemon'
    Write-Host '5. Start factor dashboard'
    Write-Host '6. Start Freqtrade auto bot'
    Write-Host '7. Open reports folder'
    Write-Host '8. Open fast log'
    Write-Host '9. Open stable log'
    Write-Host '10. Open guide'
    Write-Host '11. Open dashboard in browser'
    Write-Host '12. Open Freqtrade bot API in browser'
    Write-Host '13. Open GUI control center'
    Write-Host '0. Exit'
    Write-Host ''

    $choice = Read-Host 'Select'
    switch ($choice) {
        '1' {
            powershell -ExecutionPolicy Bypass -File (Join-Path $root 'start-openclaw-factor-daemon-fast.ps1')
            Pause-And-Return
        }
        '2' {
            powershell -ExecutionPolicy Bypass -File (Join-Path $root 'stop-openclaw-factor-daemon-fast.ps1')
            Pause-And-Return
        }
        '3' {
            powershell -ExecutionPolicy Bypass -File (Join-Path $root 'start-openclaw-factor-daemon-stable.ps1')
            Pause-And-Return
        }
        '4' {
            powershell -ExecutionPolicy Bypass -File (Join-Path $root 'stop-openclaw-factor-daemon-stable.ps1')
            Pause-And-Return
        }
        '5' {
            Start-Process powershell -ArgumentList @('-ExecutionPolicy', 'Bypass', '-File', (Join-Path $root 'start-factor-lab.ps1'))
        }
        '6' {
            powershell -ExecutionPolicy Bypass -File (Join-Path $root 'start-openclaw-auto-bot.ps1')
            Pause-And-Return
        }
        '7' {
            Start-Process explorer $reportRoot
        }
        '8' {
            if (Test-Path $fastLogPath) {
                Start-Process notepad $fastLogPath
            }
            else {
                Write-Host 'Fast log file not found yet.' -ForegroundColor Yellow
                Pause-And-Return
            }
        }
        '9' {
            if (Test-Path $stableLogPath) {
                Start-Process notepad $stableLogPath
            }
            else {
                Write-Host 'Stable log file not found yet.' -ForegroundColor Yellow
                Pause-And-Return
            }
        }
        '10' {
            Start-Process notepad $guidePath
        }
        '11' {
            Start-Process $dashboardUrl
        }
        '12' {
            Start-Process $botUrl
        }
        '13' {
            Start-Process powershell -ArgumentList @('-ExecutionPolicy', 'Bypass', '-Command', "py `"$root\start-openclaw-control-center-gui.py`"")
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
