$ErrorActionPreference = "Stop"

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
  python -m venv .venv
}

& .\.venv\Scripts\python -m pip install -r requirements.txt

$venvRoot = (Resolve-Path ".\.venv").Path
$venvSitePackages = (Resolve-Path ".\.venv\Lib\site-packages").Path
$pyvenvConfig = ".\.venv\pyvenv.cfg"
$basePythonHome = ""
if (Test-Path $pyvenvConfig) {
  $homeLine = Get-Content $pyvenvConfig | Where-Object { $_ -match '^\s*home\s*=' } | Select-Object -First 1
  if ($homeLine) {
    $basePythonHome = ($homeLine -replace '^\s*home\s*=\s*', '').Trim()
  }
}
$basePythonGui = if ($basePythonHome) { Join-Path $basePythonHome "pythonw.exe" } else { "" }
$pythonGui = if (Test-Path $basePythonGui) { $basePythonGui } elseif (Test-Path ".\.venv\Scripts\pythonw.exe") { ".\.venv\Scripts\pythonw.exe" } else { ".\.venv\Scripts\python.exe" }

$existing = Get-CimInstance Win32_Process |
  Where-Object {
    $_.Name -in @("pythonw.exe", "python.exe") -and
    $_.CommandLine -match "desktop_webview.py"
  }

foreach ($process in $existing) {
  try {
    Stop-Process -Id $process.ProcessId -Force -ErrorAction Stop
  } catch {
  }
}

foreach ($process in $existing) {
  try {
    Wait-Process -Id $process.ProcessId -Timeout 5 -ErrorAction Stop
  } catch {
  }
}

$pythonPathParts = @((Resolve-Path ".").Path, $venvSitePackages)
if ($env:PYTHONPATH) {
  $pythonPathParts += $env:PYTHONPATH
}
$env:VIRTUAL_ENV = $venvRoot
$env:PYTHONPATH = ($pythonPathParts | Where-Object { $_ } | Select-Object -Unique) -join ';'
$env:PATH = ((Join-Path $venvRoot "Scripts") + ';' + $env:PATH)

Start-Process -FilePath $pythonGui -ArgumentList "desktop_webview.py" -WorkingDirectory (Get-Location)
