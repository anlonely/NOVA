$ErrorActionPreference = "Stop"

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
  python -m venv .venv
}

& .\.venv\Scripts\python -m pip install -r requirements.txt

$pythonGui = ".\.venv\Scripts\pythonw.exe"
if (Test-Path $pythonGui) {
  Start-Process -FilePath $pythonGui -ArgumentList "app.py" -WorkingDirectory (Get-Location)
} else {
  Start-Process -FilePath ".\.venv\Scripts\python.exe" -ArgumentList "app.py" -WorkingDirectory (Get-Location)
}
