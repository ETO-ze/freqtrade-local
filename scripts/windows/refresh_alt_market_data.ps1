[CmdletBinding()]
param(
    [string]$FreqtradeRoot = 'D:\Playground\freqtrade-local',
    [string]$BaseConfigPath = 'D:\Playground\freqtrade-local\user_data\config.backtest.okx-futures-alt-local-wide.json',
    [string]$DockerImage = 'freqtradeorg/freqtrade:stable',
    [int]$Days = 180,
    [string]$ExtraPairs = 'BTC/USDT:USDT,ETH/USDT:USDT',
    [string]$Timeframes = '3m,5m,15m,1h,4h,1d',
    [switch]$Prepend,
    [int]$MaxAttempts = 3,
    [int]$RetryDelaySeconds = 30,
    [int]$MaxCacheAgeHours = 12,
    [double]$MinCacheCoveragePct = 70.0,
    [switch]$DisableCachedFallback
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

function Get-PairStem {
    param([string]$Pair)
    return $Pair.Replace('/', '_').Replace(':', '_')
}

function Test-RecentMarketCache {
    param(
        [string]$DataDir,
        [string[]]$Pairs,
        [string]$PrimaryTimeframe,
        [int]$MaxAgeHours,
        [double]$MinCoveragePct
    )

    $futuresDir = Join-Path $DataDir 'futures'
    if (-not (Test-Path $futuresDir)) {
        return [pscustomobject]@{
            ok = $false
            recent = 0
            total = $Pairs.Count
            coverage_pct = 0.0
            newest = $null
            reason = "futures data directory not found"
        }
    }

    $cutoff = (Get-Date).AddHours(-1 * [math]::Max($MaxAgeHours, 1))
    $recent = 0
    $newest = $null
    foreach ($pair in $Pairs) {
        $stem = Get-PairStem -Pair $pair
        $path = Join-Path $futuresDir "$stem-$PrimaryTimeframe-futures.feather"
        if (-not (Test-Path $path)) {
            continue
        }
        $item = Get-Item $path
        if ($null -eq $newest -or $item.LastWriteTime -gt $newest) {
            $newest = $item.LastWriteTime
        }
        if ($item.LastWriteTime -ge $cutoff -and $item.Length -gt 0) {
            $recent += 1
        }
    }
    $total = [math]::Max($Pairs.Count, 1)
    $coverage = [math]::Round(($recent / $total) * 100.0, 2)
    return [pscustomobject]@{
        ok = ($coverage -ge $MinCoveragePct)
        recent = $recent
        total = $Pairs.Count
        coverage_pct = $coverage
        newest = $newest
        reason = "recent $PrimaryTimeframe futures cache coverage $coverage%"
    }
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
if ($Prepend) {
    Write-Host "[refresh-alt-market-data] Prepend mode enabled for long-history backfill." -ForegroundColor Cyan
}

$downloadArgs = @(
    'run', '--rm',
    '-v', "${userDataDir}:/freqtrade/user_data",
    $DockerImage,
    'download-data',
    '--userdir', '/freqtrade/user_data',
    '--datadir', '/freqtrade/user_data/data/okx',
    '--exchange', 'okx',
    '--trading-mode', 'futures',
    '--pairs'
)
$downloadArgs += $pairs
$downloadArgs += @(
    '--days', $Days,
    '--timeframes'
)
$downloadArgs += $timeframesList
$downloadArgs += @(
    '--data-format-ohlcv', 'feather',
    '--candle-types', 'futures', 'mark', 'funding_rate'
)
if ($Prepend) {
    $downloadArgs += '--prepend'
}

$success = $false
$lastExitCode = 0
$attempts = [math]::Max($MaxAttempts, 1)
for ($attempt = 1; $attempt -le $attempts; $attempt++) {
    Write-Host "[refresh-alt-market-data] download-data attempt $attempt/$attempts." -ForegroundColor Cyan
    & docker @downloadArgs
    $lastExitCode = $LASTEXITCODE
    if ($lastExitCode -eq 0) {
        $success = $true
        break
    }
    if ($attempt -lt $attempts) {
        Write-Warning "[refresh-alt-market-data] download-data failed with exit code $lastExitCode. Retrying in $RetryDelaySeconds seconds."
        Start-Sleep -Seconds ([math]::Max($RetryDelaySeconds, 1))
    }
}

if (-not $success) {
    if (-not $DisableCachedFallback.IsPresent) {
        $primaryTimeframe = if ($timeframesList -contains '5m') { '5m' } else { $timeframesList[0] }
        $cacheStatus = Test-RecentMarketCache `
            -DataDir $dataDir `
            -Pairs $pairs `
            -PrimaryTimeframe $primaryTimeframe `
            -MaxAgeHours $MaxCacheAgeHours `
            -MinCoveragePct $MinCacheCoveragePct
        if ($cacheStatus.ok) {
            Write-Warning ("[refresh-alt-market-data] download-data failed with exit code {0}, but cached data is acceptable: {1}/{2} recent files ({3}%). Newest: {4}. Continuing with cache." -f $lastExitCode, $cacheStatus.recent, $cacheStatus.total, $cacheStatus.coverage_pct, $cacheStatus.newest)
            exit 0
        }
        Write-Warning ("[refresh-alt-market-data] cached data is not acceptable: {0}" -f $cacheStatus.reason)
    }
    throw "freqtrade download-data failed with exit code $lastExitCode"
}

Write-Host "[refresh-alt-market-data] Data refresh completed." -ForegroundColor Green


