$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $root 'stop-openclaw-daemon-common.ps1') -DaemonName 'factor-daemon-stable' -DisplayName 'stable'
