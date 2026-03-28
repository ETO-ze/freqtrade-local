$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$userData = Join-Path $root 'user_data'
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

Write-Host "Started freqtrade-mainstream-auto on http://127.0.0.1:8082" -ForegroundColor Cyan
