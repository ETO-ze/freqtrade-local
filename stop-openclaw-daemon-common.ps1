[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$DaemonName,
    [Parameter(Mandatory = $true)]
    [string]$DisplayName,
    [string]$StateDir = '',
    [string]$SharedRunLockName = 'openclaw-ml-workflow.lock'
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($StateDir)) {
    $root = Split-Path -Parent $MyInvocation.MyCommand.Path
    $StateDir = Join-Path $root 'reports\daemon'
}

if (-not (Test-Path $StateDir)) {
    Write-Host 'Daemon state directory does not exist.' -ForegroundColor Yellow
    exit 0
}

$stopPath = Join-Path $StateDir "$DaemonName.stop"
$pidPath = Join-Path $StateDir "$DaemonName.pid"
$lockPath = Join-Path $StateDir "$DaemonName.lock"
$statusPath = Join-Path $StateDir "$DaemonName-status.json"
$sharedLockPath = Join-Path $StateDir $SharedRunLockName

function Get-DaemonProcesses {
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            ($_.Name -in @('powershell.exe', 'pwsh.exe')) -and
            $_.CommandLine -match 'freqtrade-factor-daemon\.ps1' -and
            $_.CommandLine -match [regex]::Escape($DaemonName)
        }
}

function Test-SharedLockOwnedByDaemon {
    if (-not (Test-Path $sharedLockPath)) {
        return $false
    }
    $text = Get-Content $sharedLockPath -ErrorAction SilentlyContinue | Select-Object -First 1
    return ([string]$text).StartsWith("$DaemonName pid=")
}

function Stop-WorkflowDockerContainers {
    $rows = @()
    try {
        $rows = docker ps --no-trunc --format "{{.ID}}`t{{.Image}}`t{{.Names}}`t{{.Command}}" 2>$null
    }
    catch {
        return
    }

    foreach ($row in $rows) {
        $parts = [string]$row -split "`t", 4
        if ($parts.Count -lt 4) {
            continue
        }
        $id = $parts[0]
        $image = $parts[1]
        $name = $parts[2]
        $command = $parts[3]
        if ($name -in @('freqtrade-openclaw-auto', 'freqtrade-mainstream-auto')) {
            continue
        }
        $isWorkflowContainer = (
            $image -eq 'freqtrade-local-ml-gpu:latest' -or
            ($image -eq 'freqtradeorg/freqtrade:stable' -and $command -match 'backtesting')
        )
        if (-not $isWorkflowContainer) {
            continue
        }
        try {
            docker stop $id | Out-Null
            Write-Host "Stopped temporary workflow container: $name ($id)" -ForegroundColor Cyan
        }
        catch {
            Write-Host "Failed to stop temporary workflow container $name ($id): $($_.Exception.Message)" -ForegroundColor Yellow
        }
    }
}

Set-Content -Path $stopPath -Value 'stop' -Encoding ASCII
Write-Host "Stop signal written: $stopPath" -ForegroundColor Cyan

if (Test-Path $pidPath) {
    $pidValue = Get-Content $pidPath -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($pidValue) {
        Write-Host "Daemon PID: $pidValue" -ForegroundColor Cyan
    }
}

$sharedLockWasOwned = Test-SharedLockOwnedByDaemon
$matchingDaemons = @(Get-DaemonProcesses)
$hadMatchingDaemon = $matchingDaemons.Count -gt 0

foreach ($daemon in $matchingDaemons) {
    try {
        Stop-Process -Id $daemon.ProcessId -Force -ErrorAction Stop
        Write-Host "Stopped $DisplayName daemon PID: $($daemon.ProcessId)" -ForegroundColor Cyan
    }
    catch {
        Write-Host "Failed to stop $DisplayName daemon PID $($daemon.ProcessId): $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

if (Test-Path $pidPath) {
    $pidValue = Get-Content $pidPath -ErrorAction SilentlyContinue | Select-Object -First 1
    $pidNumber = 0
    if ([int]::TryParse([string]$pidValue, [ref]$pidNumber)) {
        $pidProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$pidNumber" -ErrorAction SilentlyContinue
        if ($pidProcess -and $pidProcess.CommandLine -match 'freqtrade-factor-daemon\.ps1' -and $pidProcess.CommandLine -match [regex]::Escape($DaemonName)) {
            try {
                Stop-Process -Id $pidNumber -Force -ErrorAction Stop
                Write-Host "Stopped $DisplayName daemon PID from pid file: $pidNumber" -ForegroundColor Cyan
            }
            catch {
                Write-Host "Failed to stop $DisplayName daemon PID from pid file $pidNumber`: $($_.Exception.Message)" -ForegroundColor Yellow
            }
        }
    }
}

Start-Sleep -Milliseconds 800
$stillRunning = @(Get-DaemonProcesses)
if ($stillRunning.Count -gt 0) {
    Write-Host "$DisplayName daemon still has $($stillRunning.Count) matching process(es) after stop attempt." -ForegroundColor Yellow
}

if ($hadMatchingDaemon -or $sharedLockWasOwned -or (Test-SharedLockOwnedByDaemon) -or -not (Test-Path $sharedLockPath)) {
    Stop-WorkflowDockerContainers
    Remove-Item $sharedLockPath -Force -ErrorAction SilentlyContinue
}

foreach ($path in @($pidPath, $lockPath, $stopPath)) {
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

Write-Host "Stopped $DisplayName daemon and cleaned stale state." -ForegroundColor Cyan
