[CmdletBinding()]
param(
    [string]$FreqtradeRoot = 'C:\Users\Administrator\Documents\Playground\freqtrade-local',
    [string]$WorkflowScriptPath = 'C:\Users\Administrator\Documents\Playground\openclaw\scripts\freqtrade-daily-ml-screen.ps1',
    [object[]]$TopNs = @(12, 15, 18, 20),
    [string]$StrategyName = 'AlternativeHunter'
)

$ErrorActionPreference = 'Stop'

$normalizedTopNs = [System.Collections.Generic.List[int]]::new()
foreach ($rawTopN in $TopNs) {
    if ($null -eq $rawTopN) {
        continue
    }

    if ($rawTopN -is [System.Array]) {
        foreach ($nestedTopN in $rawTopN) {
            if ($null -eq $nestedTopN) {
                continue
            }
            $parsedNestedValue = 0
            if (-not [int]::TryParse(([string]$nestedTopN).Trim(), [ref]$parsedNestedValue)) {
                throw "Invalid top_n value: $nestedTopN"
            }
            $normalizedTopNs.Add($parsedNestedValue)
        }
        continue
    }

    $parts = ([string]$rawTopN) -split '[,;|\s]+'
    foreach ($part in $parts) {
        $candidate = $part.Trim()
        if ([string]::IsNullOrWhiteSpace($candidate)) {
            continue
        }

        $parsedValue = 0
        if (-not [int]::TryParse($candidate, [ref]$parsedValue)) {
            throw "Invalid top_n value: $candidate"
        }
        $normalizedTopNs.Add($parsedValue)
    }
}

if ($normalizedTopNs.Count -eq 0) {
    throw 'No valid top_n values were provided.'
}

$TopNs = $normalizedTopNs.ToArray() | Sort-Object -Unique

$results = @()

foreach ($topN in $TopNs) {
    $suffix = "topn-$topN"
    Write-Host "[compare-dynamic-universe] Running top_n=$topN" -ForegroundColor Cyan

    try {
        powershell -ExecutionPolicy Bypass -File $WorkflowScriptPath `
            -FreqtradeRoot $FreqtradeRoot `
            -CandidateConfigPath "$FreqtradeRoot\user_data\config.backtest.okx-futures-alt-local-wide.json" `
            -MarketDataRefreshEnabled 0 `
            -DynamicUniverseEnabled 1 `
            -DynamicUniverseScriptPath "$FreqtradeRoot\build_dynamic_alt_universe.py" `
            -DynamicUniverseOutputConfigPath "$FreqtradeRoot\user_data\config.backtest.okx-futures-alt-local-dynamic.$suffix.generated.json" `
            -DynamicUniverseReportPath "$FreqtradeRoot\reports\openclaw-dynamic-alt-universe-$suffix.md" `
            -DynamicUniverseJsonPath "$FreqtradeRoot\reports\openclaw-dynamic-alt-universe-$suffix.json" `
            -DynamicUniverseTopN $topN `
            -StrategyName $StrategyName `
            -MlModels 'tree,rf,hgb,xgb' `
            -MlDockerImage 'freqtrade-local-ml-gpu:latest' `
            -UseGpuForMl 1 `
            -UseEvolution 0 `
            -RobustScreenCacheTtlMinutes 180 `
            -AutoSyncMaxPairs 10 `
            -AutoBacktestFreqtrade 1 `
            -AutoBacktestTimerangeMode auto `
            -AutoBacktestLookbackDays 108 `
            -MlOutputPrefix "/freqtrade/user_data/reports/ml/daily-alt-tree-model-$suffix" `
            -CombinedReportPath "$FreqtradeRoot\reports\openclaw-daily-alt-ml-$suffix.md" `
            -CombinedJsonPath "$FreqtradeRoot\reports\openclaw-daily-alt-ml-$suffix.json" `
            -StrategyUpdateReportPath "$FreqtradeRoot\reports\openclaw-strategy-update-$suffix.md" `
            -BestModelJsonPath "$FreqtradeRoot\reports\openclaw-best-model-$suffix.json" `
            -BestModelReportPath "$FreqtradeRoot\reports\openclaw-best-model-$suffix.md" `
            -AutoBacktestReportPath "$FreqtradeRoot\reports\openclaw-auto-backtest-$suffix.md" `
            -AutoBacktestJsonReportPath "$FreqtradeRoot\reports\openclaw-auto-backtest-$suffix.json" `
            -ApprovalReportPath "$FreqtradeRoot\reports\openclaw-auto-approval-$suffix.md" `
            -CandidateTargetConfigPath "$FreqtradeRoot\user_data\config.openclaw-candidate-$suffix.json" `
            -RuntimePolicyPath "$FreqtradeRoot\user_data\model_runtime_policy.json" `
            -TradeFeedbackIsolated 1 `
            -TradeFeedbackReportPath "$FreqtradeRoot\reports\openclaw-trade-feedback-$suffix.md" `
            -TradeFeedbackJsonPath "$FreqtradeRoot\reports\openclaw-trade-feedback-$suffix.json" `
            -TradeFeedbackPolicyCandidatePath "$FreqtradeRoot\reports\openclaw-trade-feedback-policy-$suffix.json" `
            -PublishDashboardPublicData 0 `
            -RemoteSyncServer 0 `
            -UpdateLatestAliases 0 | Out-Null
    }
    catch {
        Write-Host ("[compare-dynamic-universe] Workflow threw for top_n={0}: {1}" -f $topN, $_.Exception.Message) -ForegroundColor Yellow
    }

    $backtestPath = "$FreqtradeRoot\reports\openclaw-auto-backtest-$suffix.json"
    $combinedPath = "$FreqtradeRoot\reports\openclaw-daily-alt-ml-$suffix.json"
    $bestModelPath = "$FreqtradeRoot\reports\openclaw-best-model-$suffix.json"
    $universePath = "$FreqtradeRoot\reports\openclaw-dynamic-alt-universe-$suffix.json"
    $approvalPath = "$FreqtradeRoot\reports\openclaw-auto-approval-$suffix.md"

    $backtest = $null
    if (Test-Path $backtestPath) {
        $backtest = Get-Content $backtestPath -Raw | ConvertFrom-Json
    }
    $combined = Get-Content $combinedPath -Raw | ConvertFrom-Json
    $bestModel = Get-Content $bestModelPath -Raw | ConvertFrom-Json
    $universe = $null
    if (Test-Path $universePath) {
        $universe = Get-Content $universePath -Raw | ConvertFrom-Json
    }
    $approvalSummary = ''
    if (Test-Path $approvalPath) {
        $approvalSummary = (Get-Content $approvalPath -Raw).Trim()
    }

    $results += [pscustomobject]@{
        top_n = $topN
        freshest_market_timestamp = $(if ($universe) { [string]$universe.freshest_market_timestamp } else { $null })
        selected_universe_pairs = $(if ($universe) { @($universe.selected_pairs) } else { @() })
        profit_pct = $(if ($backtest) { [double]$backtest.metrics.total_profit_pct } else { $null })
        profit_factor = $(if ($backtest) { [double]$backtest.metrics.profit_factor } else { $null })
        max_drawdown_pct = $(if ($backtest) { [double]$backtest.metrics.max_drawdown_pct } else { $null })
        trade_count = $(if ($backtest) { [int]$backtest.metrics.trade_count } else { $null })
        best_model = [string]$bestModel.selected_model
        tradable_pairs = @($combined.tradable | ForEach-Object { $_.Pair })
        observe_pairs = @($combined.observe | ForEach-Object { $_.Pair })
        approval_summary = $approvalSummary
    }
}

$jsonPath = "$FreqtradeRoot\reports\openclaw-dynamic-topn-compare.json"
$mdPath = "$FreqtradeRoot\reports\openclaw-dynamic-topn-compare.md"

$results | ConvertTo-Json -Depth 6 | Set-Content -Path $jsonPath -Encoding UTF8

$lines = @()
$lines += '# OpenClaw Dynamic Universe Top-N Comparison'
$lines += ''
$lines += "- Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
$lines += "- Top Ns: $($TopNs -join ', ')"
$lines += ''
$lines += '| Top N | Fresh Data | Universe | Profit % | Profit Factor | Max Drawdown % | Trades | Best Model | Tradable | Observe |'
$lines += '| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |'
foreach ($item in $results) {
    $tradable = if ($item.tradable_pairs) { ($item.tradable_pairs -join ', ') } else { 'none' }
    $observe = if ($item.observe_pairs) { ($item.observe_pairs -join ', ') } else { 'none' }
    $freshData = if ($item.freshest_market_timestamp) { $item.freshest_market_timestamp } else { 'n/a' }
    $universeCount = @($item.selected_universe_pairs).Count
    $lines += "| $($item.top_n) | $freshData | $universeCount | $($item.profit_pct) | $($item.profit_factor) | $($item.max_drawdown_pct) | $($item.trade_count) | $($item.best_model) | $tradable | $observe |"
    if (-not [string]::IsNullOrWhiteSpace($item.approval_summary)) {
        $approvalCompact = $item.approval_summary.Replace("`r", ' ').Replace("`n", ' ')
        $lines += "|  |  |  |  |  |  |  | Approval | $approvalCompact |  |"
    }
}

[System.IO.File]::WriteAllLines($mdPath, $lines, [System.Text.UTF8Encoding]::new($false))

Write-Host "[compare-dynamic-universe] Wrote $jsonPath" -ForegroundColor Green
Write-Host "[compare-dynamic-universe] Wrote $mdPath" -ForegroundColor Green
