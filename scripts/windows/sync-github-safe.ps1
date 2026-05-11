param(
    [string]$ProjectRoot = (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))),
    [string]$Message = "",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[github-sync] $Message"
}

function Invoke-Git {
    param([string[]]$Arguments)
    & git -C $ProjectRoot @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "git $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
    }
}

if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot ".git"))) {
    throw "Not a git repository: $ProjectRoot"
}

$branch = (& git -C $ProjectRoot branch --show-current).Trim()
if ([string]::IsNullOrWhiteSpace($branch)) {
    throw "Unable to resolve current git branch."
}

$status = (& git -C $ProjectRoot status --porcelain)
if (-not $status) {
    Write-Step "No local changes to sync."
    exit 0
}

$excludedRegexes = @(
    "^backups/",
    "^reports/",
    "^dashboard-data/",
    "^user_data/backtest_results/",
    "^user_data/backtest_cache/",
    "^user_data/data/",
    "^user_data/logs/",
    "^user_data/.*\.sqlite",
    "^user_data/config\.json$",
    "^user_data/config\.openclaw-auto.*\.json$",
    "^user_data/config\.openclaw-candidate.*\.json$",
    "^user_data/config\.autotune\..*\.json$",
    "^user_data/config\.backtest\.strategylab\.json$",
    "^user_data/config\.backtest\.okx-futures-alt-local-dynamic.*\.json$",
    "^user_data/model_runtime_policy\.json$",
    "^user_data/model_runtime_policy\.debug\.json$",
    "^user_data/model_runtime_policy\.autotune\..*\.json$",
    "^user_data/model_runtime_tuning\.auto\.json$",
    "^server\.openclaw-sync\.local\.json$",
    "^openclaw\.notification\.json$",
    "^site/dashboard/node_modules/",
    "^site/dashboard/dist/",
    "(^|/)__pycache__/"
)

Write-Step "Staging safe project changes on branch '$branch'."
Invoke-Git @("reset", "--")

$candidates = @()
$candidates += (& git -C $ProjectRoot ls-files -m -o -d --exclude-standard)
$safeFiles = @()
foreach ($file in ($candidates | Sort-Object -Unique)) {
    if ([string]::IsNullOrWhiteSpace($file)) {
        continue
    }
    $normalized = $file -replace "\\", "/"
    $blocked = $false
    foreach ($pattern in $excludedRegexes) {
        if ($normalized -match $pattern) {
            $blocked = $true
            break
        }
    }
    if (-not $blocked) {
        $safeFiles += $file
    }
}

if (-not $safeFiles) {
    Write-Step "No safe files to stage. Runtime/cache/secret files were ignored."
    exit 0
}

for ($i = 0; $i -lt $safeFiles.Count; $i += 80) {
    $end = [Math]::Min($i + 79, $safeFiles.Count - 1)
    $chunk = @($safeFiles[$i..$end])
    Invoke-Git (@("add", "--") + $chunk)
}

$staged = (& git -C $ProjectRoot diff --cached --name-only)
if (-not $staged) {
    Write-Step "No safe files staged. Runtime/cache/secret files were ignored."
    exit 0
}

$blockedPatterns = @(
    "^server\.openclaw-sync\.local\.json$",
    "^openclaw\.notification\.json$",
    "^user_data/config\.json$",
    "^user_data/config\.openclaw-auto.*\.json$",
    "^user_data/config\.autotune\..*\.json$",
    "^user_data/model_runtime_policy\.json$",
    "^user_data/model_runtime_policy\.autotune\..*\.json$",
    "^user_data/model_runtime_tuning\.auto\.json$",
    "^reports/",
    "^backups/",
    "^dashboard-data/"
)

foreach ($file in $staged) {
    $normalized = $file -replace "\\", "/"
    foreach ($pattern in $blockedPatterns) {
        if ($normalized -match $pattern) {
            Invoke-Git @("reset", "--")
            throw "Blocked sensitive/runtime file staged unexpectedly: $file"
        }
    }
}

$secretHits = (& git -C $ProjectRoot diff --cached -U0 -- . ":(exclude)sync-github-safe.ps1" ":(exclude)scripts/windows/sync-github-safe.ps1" | Select-String -Pattern "github_pat_|ghp_[A-Za-z0-9_]{20,}|sk-proj-[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9]{32,}|xox[baprs]-[A-Za-z0-9-]{20,}" -AllMatches)
if ($secretHits) {
    Invoke-Git @("reset", "--")
    throw "Potential secret detected in staged diff. Staging was reset; inspect changes manually."
}

Write-Step "Files staged:"
$staged | ForEach-Object { Write-Host "  $_" }

if ($DryRun) {
    Invoke-Git @("reset", "--")
    Write-Step "Dry run complete. Staging reset; nothing committed."
    exit 0
}

if ([string]::IsNullOrWhiteSpace($Message)) {
    $Message = "chore: sync OpenClaw updates $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
}

Write-Step "Committing: $Message"
Invoke-Git @("commit", "-m", $Message)

Write-Step "Pushing to origin/$branch"
Invoke-Git @("push", "origin", $branch)

Write-Step "GitHub sync complete."


