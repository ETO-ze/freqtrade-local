$ErrorActionPreference = 'Stop'

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent (Split-Path -Parent $scriptRoot)
& (Join-Path $scriptRoot 'stop-openclaw-daemon-common.ps1') -DaemonName 'factor-daemon-stable' -DisplayName 'stable'


