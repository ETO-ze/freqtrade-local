[CmdletBinding()]
param(
    [ValidateSet('normal', 'boost')]
    [string]$Mode = 'normal'
)

$ErrorActionPreference = 'Stop'

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent (Split-Path -Parent $scriptRoot)

if ($Mode -eq 'boost') {
    $fastInterval = 20
    $fastDelay = 5
    $stableInterval = 90
    $stableDelay = 15
    Write-Host '[training-speed] Switching to boost mode: fast=20m, stable=90m.' -ForegroundColor Cyan
}
else {
    $fastInterval = 60
    $fastDelay = 45
    $stableInterval = 180
    $stableDelay = 0
    Write-Host '[training-speed] Switching to normal mode: fast=60m, stable=180m.' -ForegroundColor Cyan
}

Write-Host '[training-speed] Restarting fast/stable daemons to apply new intervals.' -ForegroundColor Cyan

& (Join-Path $scriptRoot 'stop-openclaw-factor-daemon-fast.ps1') | Out-Host
& (Join-Path $scriptRoot 'stop-openclaw-factor-daemon-stable.ps1') | Out-Host

Start-Sleep -Seconds 2

& (Join-Path $scriptRoot 'start-openclaw-factor-daemon-fast.ps1') `
    -IntervalMinutes $fastInterval `
    -StartupDelaySeconds $fastDelay `
    -ForceRestart | Out-Host

& (Join-Path $scriptRoot 'start-openclaw-factor-daemon-stable.ps1') `
    -IntervalMinutes $stableInterval `
    -StartupDelaySeconds $stableDelay `
    -ForceRestart | Out-Host

Write-Host '[training-speed] Done.' -ForegroundColor Cyan


