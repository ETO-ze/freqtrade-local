$ErrorActionPreference = "SilentlyContinue"

docker rm -f freqtrade-mainstream-auto *> $null
Write-Host "Stopped freqtrade-mainstream-auto" -ForegroundColor Yellow
