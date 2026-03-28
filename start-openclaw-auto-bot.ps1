$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$userData = Join-Path $root 'user_data'
$configPath = '/freqtrade/user_data/config.openclaw-auto.json'
$dbPath = 'sqlite:////freqtrade/user_data/tradesv3-openclaw-auto.sqlite'
$logPath = '/freqtrade/user_data/logs/freqtrade-openclaw-auto.log'

try {
  docker rm -f freqtrade-openclaw-auto *> $null
} catch {
  # Ignore cleanup errors when the container does not exist yet.
}

docker run -d `
  --name freqtrade-openclaw-auto `
  --restart unless-stopped `
  -p 127.0.0.1:8081:8080 `
  -v "${userData}:/freqtrade/user_data" `
  freqtradeorg/freqtrade:stable `
  trade `
  --logfile $logPath `
  --db-url $dbPath `
  --config $configPath `
  --strategy AlternativeHunter

Write-Host "Started freqtrade-openclaw-auto on http://127.0.0.1:8081" -ForegroundColor Cyan
