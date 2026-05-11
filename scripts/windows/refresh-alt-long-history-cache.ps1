[CmdletBinding()]
param(
    [string]$FreqtradeRoot = 'D:\Playground\freqtrade-local',
    [string]$BaseConfigPath = '',
    [string]$StartDate = '20250101',
    [string]$ExtraPairs = 'BTC/USDT:USDT,ETH/USDT:USDT',
    [string]$Timeframes = '3m,5m,15m,1h,4h,1d'
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($BaseConfigPath)) {
    $dynamicConfig = Join-Path $FreqtradeRoot 'user_data\config.backtest.okx-futures-alt-local-dynamic.generated.json'
    $wideConfig = Join-Path $FreqtradeRoot 'user_data\config.backtest.okx-futures-alt-local-wide.json'
    $BaseConfigPath = if (Test-Path $dynamicConfig) { $dynamicConfig } else { $wideConfig }
}

$start = [datetime]::ParseExact($StartDate, 'yyyyMMdd', [Globalization.CultureInfo]::InvariantCulture)
$today = [datetime]::UtcNow.Date
$days = [math]::Max(1, [int](($today - $start).TotalDays) + 2)
$refreshScript = Join-Path $FreqtradeRoot 'refresh_alt_market_data.ps1'

Write-Host "[long-history-cache] Base config: $BaseConfigPath" -ForegroundColor Cyan
Write-Host "[long-history-cache] Target cache window: $StartDate to now, days=$days" -ForegroundColor Cyan

powershell -ExecutionPolicy Bypass -File $refreshScript `
    -FreqtradeRoot $FreqtradeRoot `
    -BaseConfigPath $BaseConfigPath `
    -Days $days `
    -ExtraPairs $ExtraPairs `
    -Timeframes $Timeframes `
    -Prepend

if ($LASTEXITCODE -ne 0) {
    throw "Long-history cache refresh failed with exit code $LASTEXITCODE"
}

Write-Host "[long-history-cache] Completed." -ForegroundColor Green


