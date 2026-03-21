$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host "Starting Factor Lab on http://127.0.0.1:8501" -ForegroundColor Cyan
py -m streamlit run "$root\factor_lab.py" --server.address 127.0.0.1 --server.port 8501

