[CmdletBinding()]
param(
    [string]$ProjectRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path),
    [string]$SettingsPath = '',
    [string]$SourceConfigPath = '',
    [ValidateSet('if-running', 'always', 'never')]
    [string]$RestartBot = 'if-running',
    [string]$Mode = 'manual'
)

$ErrorActionPreference = 'Stop'

$pythonScript = Join-Path $ProjectRoot 'sync_openclaw_runtime_to_server.py'
if (-not (Test-Path $pythonScript)) {
    throw "Sync script not found: $pythonScript"
}

$arguments = @($pythonScript, '--project-root', $ProjectRoot, '--restart-bot', $RestartBot, '--mode', $Mode)
if ($SettingsPath) {
    $arguments += @('--settings-path', $SettingsPath)
}
if ($SourceConfigPath) {
    $arguments += @('--source-config-path', $SourceConfigPath)
}

& py @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Remote sync failed with exit code $LASTEXITCODE"
}
