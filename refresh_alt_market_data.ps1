[CmdletBinding()]
param(
    [string]$FreqtradeRoot = 'C:\Users\Administrator\Documents\Playground\freqtrade-local',
    [string]$BaseConfigPath = 'C:\Users\Administrator\Documents\Playground\freqtrade-local\user_data\config.backtest.okx-futures-alt-local-wide.json',
    [string]$DockerImage = 'freqtradeorg/freqtrade:stable',
    [int]$Days = 180,
    [string]$ExtraPairs = 'BTC/USDT:USDT,ETH/USDT:USDT',
    [string]$Timeframes = '3m,5m,15m,1h,4h,1d'
)

$ErrorActionPreference = 'Stop'

function Get-UniquePairs {
    param(
        [string[]]$PrimaryPairs,
        [string[]]$SecondaryPairs
    )

    $seen = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    $result = New-Object System.Collections.Generic.List[string]
    foreach ($pair in @($PrimaryPairs + $SecondaryPairs)) {
        if ([string]::IsNullOrWhiteSpace($pair)) {
            continue
        }
        $trimmed = $pair.Trim()
        if ($seen.Add($trimmed)) {
            [void]$result.Add($trimmed)
        }
    }
    return @($result)
}

$config = Get-Content $BaseConfigPath -Raw | ConvertFrom-Json
$basePairs = @($config.exchange.pair_whitelist)
$extraPairsList = @($ExtraPairs -split ',' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
$pairs = Get-UniquePairs -PrimaryPairs $basePairs -SecondaryPairs $extraPairsList
$timeframesList = @($Timeframes -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
$dataDir = Join-Path $FreqtradeRoot 'user_data\data\okx'
$userDataDir = Join-Path $FreqtradeRoot 'user_data'

Write-Host "[refresh-alt-market-data] Refreshing $($pairs.Count) pairs for $Days days." -ForegroundColor Cyan
Write-Host "[refresh-alt-market-data] Timeframes: $($timeframesList -join ', ')" -ForegroundColor Cyan

docker run --rm `
    -v "${userDataDir}:/freqtrade/user_data" `
    $DockerImage `
    download-data `
    --userdir /freqtrade/user_data `
    --datadir /freqtrade/user_data/data/okx `
    --exchange okx `
    --trading-mode futures `
    --pairs $pairs `
    --days $Days `
    --timeframes $timeframesList `
    --data-format-ohlcv feather `
    --candle-types futures mark funding_rate

if ($LASTEXITCODE -ne 0) {
    throw "freqtrade download-data failed with exit code $LASTEXITCODE"
}

Write-Host "[refresh-alt-market-data] Data refresh completed." -ForegroundColor Green
