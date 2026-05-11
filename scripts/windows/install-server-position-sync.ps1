param(
    [string]$ProjectRoot = (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))),
    [string]$SettingsPath = "",
    [int]$IntervalSeconds = 60,
    [switch]$RunOnce
)

$ErrorActionPreference = "Stop"

if (-not $SettingsPath) {
    $SettingsPath = Join-Path $ProjectRoot "server.openclaw-sync.local.json"
}

$script = Join-Path $ProjectRoot "scripts\workflows\install_server_position_sync.py"
if (-not (Test-Path -LiteralPath $script)) {
    throw "Missing installer script: $script"
}

$args = @(
    $script,
    "--project-root", $ProjectRoot,
    "--settings-path", $SettingsPath,
    "--interval-seconds", "$IntervalSeconds"
)
if ($RunOnce) {
    $args += "--run-once"
}

py @args


