[CmdletBinding()]
param(
    [ValidateSet('normal', 'boost')]
    [string]$Mode = 'normal'
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

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

& (Join-Path $root 'stop-openclaw-factor-daemon-fast.ps1') | Out-Host
& (Join-Path $root 'stop-openclaw-factor-daemon-stable.ps1') | Out-Host

Start-Sleep -Seconds 2

& (Join-Path $root 'start-openclaw-factor-daemon-fast.ps1') `
    -IntervalMinutes $fastInterval `
    -StartupDelaySeconds $fastDelay `
    -ForceRestart | Out-Host

& (Join-Path $root 'start-openclaw-factor-daemon-stable.ps1') `
    -IntervalMinutes $stableInterval `
    -StartupDelaySeconds $stableDelay `
    -ForceRestart | Out-Host

Write-Host '[training-speed] Done.' -ForegroundColor Cyan
