param(
    [string]$SourceRoot = "C:\Users\Administrator\Documents\Playground",
    [string]$TargetRoot = "D:\Playground"
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[migration] $Message"
}

function Ensure-TargetReady {
    param([string]$Name)
    $target = Join-Path $TargetRoot $Name
    if (-not (Test-Path -LiteralPath $target)) {
        throw "Target directory missing: $target"
    }

    $children = Get-ChildItem -LiteralPath $target -Force -ErrorAction Stop
    if (($children | Measure-Object).Count -eq 0) {
        throw "Target directory is empty, refusing to replace source: $target"
    }
}

function Replace-WithJunction {
    param(
        [string]$Name
    )

    Ensure-TargetReady -Name $Name

    $source = Join-Path $SourceRoot $Name
    $target = Join-Path $TargetRoot $Name

    if (Test-Path -LiteralPath $source) {
        $item = Get-Item -LiteralPath $source -Force
        if ($item.LinkType -eq "Junction") {
            Write-Step "$Name is already a junction"
            return
        }

        try {
            Remove-Item -LiteralPath $source -Recurse -Force -ErrorAction Stop
        } catch {
            throw "Cannot replace '$source'. Close Codex, PowerShell windows, Docker terminals, and any tools using Playground, then rerun this script."
        }
    }

    New-Item -ItemType Junction -Path $source -Target $target | Out-Null
    Write-Step "$source -> $target"
}

Write-Step "This script will only replace local folders with junctions. It will not mirror C: back to D:."

foreach ($name in @("freqtrade-local", "openclaw")) {
    Replace-WithJunction -Name $name
}

Write-Step "Done"
