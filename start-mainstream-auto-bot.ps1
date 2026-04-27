$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$userData = Join-Path $root 'user_data'
$hostConfigPath = Join-Path $userData 'config.mainstream-auto.json'
$configPath = '/freqtrade/user_data/config.mainstream-auto.json'
$dbPath = 'sqlite:////freqtrade/user_data/tradesv3-mainstream-auto.sqlite'
$logPath = '/freqtrade/user_data/logs/freqtrade-mainstream-auto.log'

try {
  docker rm -f freqtrade-mainstream-auto *> $null
} catch {
  # Ignore cleanup errors when the container does not exist yet.
}

docker run -d `
  --name freqtrade-mainstream-auto `
  --restart unless-stopped `
  -p 127.0.0.1:8082:8080 `
  -v "${userData}:/freqtrade/user_data" `
  freqtradeorg/freqtrade:stable `
  trade `
  --logfile $logPath `
  --db-url $dbPath `
  --config $configPath `
  --strategy MainstreamHunter

try {
  $deadline = (Get-Date).AddSeconds(75)
  $ready = $false
  do {
    Start-Sleep -Seconds 3
    try {
      Invoke-RestMethod -Method Get -Uri 'http://127.0.0.1:8082/api/v1/ping' -TimeoutSec 5 | Out-Null
      $ready = $true
    } catch {
      $ready = $false
    }
  } while (-not $ready -and (Get-Date) -lt $deadline)

  if ($ready -and (Test-Path $hostConfigPath)) {
    $config = Get-Content $hostConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $username = [string]$config.api_server.username
    $password = [string]$config.api_server.password
    if (-not [string]::IsNullOrWhiteSpace($username) -and -not [string]::IsNullOrWhiteSpace($password)) {
      $basic = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("${username}:${password}"))
      Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8082/api/v1/start' -Headers @{ Authorization = "Basic $basic" } -TimeoutSec 10 | Out-Null
      Write-Host "Requested freqtrade-mainstream-auto trader start." -ForegroundColor Cyan
    }
  }
} catch {
  Write-Warning "Container started, but API trader start request failed: $($_.Exception.Message)"
}

Write-Host "Started freqtrade-mainstream-auto on http://127.0.0.1:8082" -ForegroundColor Cyan
