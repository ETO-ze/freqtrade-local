param(
    [Parameter(Position = 0)]
    [string]$Command = "help",

    [Parameter(Position = 1)]
    [string]$Target = ""
)

$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent (Split-Path -Parent $ScriptRoot)
$WorkspaceRoot = Split-Path -Parent $RepoRoot
$ReportsRoot = Join-Path $RepoRoot "reports"
$DaemonDir = Join-Path $ReportsRoot "daemon"

function Write-Usage {
    Write-Host "ftctl commands:"
    Write-Host "  status | health"
    Write-Host "  start <fast|stable|evolution|autotune>"
    Write-Host "  stop <fast|stable|evolution|autotune>"
    Write-Host "  gui"
    Write-Host "  dashboard"
    Write-Host "  reports"
    Write-Host "  sync server"
}

function Test-PidAlive {
    param([object]$PidValue)
    if (-not $PidValue) { return $false }
    try {
        $pidInt = [int]$PidValue
        return [bool](Get-Process -Id $pidInt -ErrorAction SilentlyContinue)
    } catch {
        return $false
    }
}

function Test-DockerReady {
    $job = Start-Job -ScriptBlock {
        docker version --format "{{.Server.Version}}" 2>$null
        if ($LASTEXITCODE -eq 0) { "ready" } else { "not-ready" }
    }
    try {
        if (Wait-Job $job -Timeout 8) {
            $result = Receive-Job $job -ErrorAction SilentlyContinue
            return ($result -contains "ready")
        }
        return $false
    } finally {
        Remove-Job $job -Force -ErrorAction SilentlyContinue
    }
}

function Read-JsonFile {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    try {
        return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    } catch {
        return $null
    }
}

function Get-DaemonStatus {
    param([string]$Name)

    $path = Join-Path $DaemonDir ("factor-daemon-{0}-status.json" -f $Name)
    $json = Read-JsonFile -Path $path
    if (-not $json) {
        return [pscustomobject]@{
            name = $Name
            status = "missing"
            pid = $null
            alive = $false
            note = ""
        }
    }

    $pidValue = $json.pid
    if (-not $pidValue) { $pidValue = $json.daemon_pid }
    [pscustomobject]@{
        name = $Name
        status = [string]$json.status
        pid = $pidValue
        alive = Test-PidAlive -PidValue $pidValue
        note = [string]$json.note
    }
}

function Show-Status {
    Write-Host "# OpenClaw Runtime Status"
    Write-Host ""
    Write-Host ("Generated at: {0}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
    Write-Host ""

    Write-Host "## Paths"
    Write-Host ("- Repo: {0}" -f $RepoRoot)
    Write-Host ("- Workspace: {0}" -f $WorkspaceRoot)
    Write-Host ""

    Write-Host "## Docker"
    Write-Host ("- Ready: {0}" -f (Test-DockerReady))
    Write-Host ""

    Write-Host "## Daemons"
    foreach ($name in @("fast", "stable", "evolution", "autotune")) {
        $s = Get-DaemonStatus -Name $name
        $line = "- factor-daemon-{0}: status={1} | pid={2} | alive={3}" -f $s.name, $s.status, $s.pid, $s.alive
        if ($s.note) { $line = "$line | note=$($s.note)" }
        Write-Host $line
    }
    Write-Host ""

    $best = Read-JsonFile -Path (Join-Path $ReportsRoot "openclaw-best-model-stable.json")
    $policy = Read-JsonFile -Path (Join-Path $RepoRoot "user_data\model_runtime_policy.json")
    $backtest = Read-JsonFile -Path (Join-Path $ReportsRoot "openclaw-auto-backtest-stable.json")

    Write-Host "## Stable Snapshot"
    if ($best) {
        $bestModelName = if ($best.best_model) { $best.best_model } elseif ($best.selected_model) { $best.selected_model } else { "N/A" }
        Write-Host ("- Best model: {0}" -f $bestModelName)
    } else {
        Write-Host "- Best model: N/A"
    }
    if ($policy) {
        $tradableCount = 0
        $observeCount = 0
        if ($policy.tradable) {
            $tradableCount = @($policy.tradable).Count
        } elseif ($policy.pairs) {
            foreach ($pair in $policy.pairs.PSObject.Properties) {
                if ([string]$pair.Value.decision -eq "tradable") { $tradableCount += 1 }
            }
        }
        if ($policy.observe) {
            $observeCount = @($policy.observe).Count
        } elseif ($policy.pairs) {
            foreach ($pair in $policy.pairs.PSObject.Properties) {
                if ([string]$pair.Value.decision -eq "observe") { $observeCount += 1 }
            }
        }
        Write-Host ("- Strategy: {0}" -f $policy.strategy)
        Write-Host ("- Tradable count: {0}" -f $tradableCount)
        Write-Host ("- Observe count: {0}" -f $observeCount)
    } else {
        Write-Host "- Runtime policy: missing"
    }
    if ($backtest) {
        Write-Host ("- Auto backtest timerange: {0}" -f $backtest.timerange)
    }
}

function Invoke-StartDaemon {
    param([string]$Name)
    $script = Join-Path $RepoRoot ("start-openclaw-factor-daemon-{0}.ps1" -f $Name)
    if (-not (Test-Path -LiteralPath $script)) { throw "Missing start script: $script" }
    powershell -ExecutionPolicy Bypass -File $script
}

function Invoke-StopDaemon {
    param([string]$Name)
    $script = Join-Path $RepoRoot ("stop-openclaw-factor-daemon-{0}.ps1" -f $Name)
    if (-not (Test-Path -LiteralPath $script)) { throw "Missing stop script: $script" }
    powershell -ExecutionPolicy Bypass -File $script
}

function Start-Gui {
    $script = Join-Path $RepoRoot "start-openclaw-control-center-gui.py"
    if (-not (Test-Path -LiteralPath $script)) { throw "Missing GUI script: $script" }
    Start-Process powershell -WindowStyle Hidden -ArgumentList @(
        "-ExecutionPolicy", "Bypass",
        "-Command", "cd /d `"$RepoRoot`"; py `"$script`""
    )
}

function Start-Dashboard {
    $script = Join-Path $RepoRoot "start-factor-lab.ps1"
    if (-not (Test-Path -LiteralPath $script)) { throw "Missing dashboard script: $script" }
    Start-Process powershell -WindowStyle Hidden -ArgumentList @(
        "-ExecutionPolicy", "Bypass",
        "-File", $script
    )
}

switch ($Command.ToLowerInvariant()) {
    "help" { Write-Usage }
    "status" { Show-Status }
    "health" { Show-Status }
    "start" {
        if ($Target -notin @("fast", "stable", "evolution", "autotune")) { throw "Unknown daemon: $Target" }
        Invoke-StartDaemon -Name $Target
    }
    "stop" {
        if ($Target -notin @("fast", "stable", "evolution", "autotune")) { throw "Unknown daemon: $Target" }
        Invoke-StopDaemon -Name $Target
    }
    "gui" { Start-Gui }
    "dashboard" { Start-Dashboard }
    "reports" {
        New-Item -ItemType Directory -Force -Path $ReportsRoot | Out-Null
        Start-Process explorer.exe $ReportsRoot
    }
    "sync" {
        if ($Target -ne "server") { throw "Usage: ftctl sync server" }
        $script = Join-Path $RepoRoot "sync-openclaw-runtime-to-server.ps1"
        if (-not (Test-Path -LiteralPath $script)) { throw "Missing sync script: $script" }
        powershell -ExecutionPolicy Bypass -File $script
    }
    default { Write-Usage; throw "Unknown command: $Command" }
}
