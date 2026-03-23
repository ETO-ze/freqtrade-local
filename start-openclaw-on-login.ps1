$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$openclawRoot = 'C:\Users\Administrator\Documents\Playground\openclaw'
$openclawProxyScript = Join-Path $openclawRoot 'start-openclaw-proxy.ps1'
$daemonDir = Join-Path $root 'reports\daemon'
$dockerDesktop = 'C:\Program Files\Docker\Docker\Docker Desktop.exe'

if (-not (Test-Path $daemonDir)) {
    New-Item -Path $daemonDir -ItemType Directory -Force | Out-Null
}

if (Test-Path $openclawProxyScript) {
    Start-Process powershell -ArgumentList @(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-File', $openclawProxyScript
    ) -WorkingDirectory $openclawRoot -WindowStyle Hidden | Out-Null
}

foreach ($stopFile in @(
    'factor-daemon-fast.stop',
    'factor-daemon-stable.stop',
    'factor-daemon-evolution.stop'
)) {
    $stopPath = Join-Path $daemonDir $stopFile
    if (Test-Path $stopPath) {
        Remove-Item $stopPath -Force -ErrorAction SilentlyContinue
    }
}

if (Test-Path $dockerDesktop) {
    Start-Process $dockerDesktop | Out-Null
}

$deadline = (Get-Date).AddMinutes(5)
$dockerReady = $false
do {
    Start-Sleep -Seconds 5
    try {
        docker version | Out-Null
        $dockerReady = $true
    }
    catch {
        $dockerReady = $false
    }
} while (-not $dockerReady -and (Get-Date) -lt $deadline)

if (-not $dockerReady) {
    throw 'Docker Desktop did not become ready in time.'
}

powershell -ExecutionPolicy Bypass -File (Join-Path $root 'start-openclaw-factor-daemon-stable.ps1')
Start-Sleep -Seconds 3
powershell -ExecutionPolicy Bypass -File (Join-Path $root 'start-openclaw-factor-daemon-fast.ps1')
Start-Sleep -Seconds 3
powershell -ExecutionPolicy Bypass -File (Join-Path $root 'start-openclaw-auto-bot.ps1')

Write-Host 'OpenClaw startup workflow completed.' -ForegroundColor Cyan
