$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$target = Join-Path $root "web_dashboard\index.html"
$python = Join-Path $root ".venv\Scripts\python.exe"
$exporter = Join-Path $root "web_dashboard\export_dashboard_state.py"

if (-not (Test-Path $target)) {
    Write-Error "Preview file not found: $target"
    exit 1
}

if ((Test-Path $python) -and (Test-Path $exporter)) {
    & $python $exporter | Out-Null
}

Start-Process $target
