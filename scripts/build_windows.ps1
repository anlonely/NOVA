$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
  python -m venv .venv
}

& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r requirements-build.txt

$cargo = Get-Command cargo -ErrorAction SilentlyContinue
if ($cargo) {
  Write-Host "Building native audio core with cargo..."
  Push-Location (Join-Path $projectRoot "native_audio_core")
  try {
    & $cargo.Source build --release
  } finally {
    Pop-Location
  }
} else {
  Write-Host "Cargo not found. Skipping native audio core build."
}

$buildDir = Join-Path $projectRoot "build"
$distDir = Join-Path $projectRoot "dist"
$releaseDir = Join-Path $projectRoot "output\release"
$bundleDir = Join-Path $distDir "NOVA-INTERP"

if (Test-Path $buildDir) {
  Remove-Item -LiteralPath $buildDir -Recurse -Force
}
if (Test-Path $distDir) {
  Remove-Item -LiteralPath $distDir -Recurse -Force
}
New-Item -ItemType Directory -Path $releaseDir -Force | Out-Null

& $venvPython -m PyInstaller --noconfirm --clean nova_interp.spec

Copy-Item -LiteralPath (Join-Path $projectRoot "config.example.json") -Destination (Join-Path $bundleDir "config.example.json") -Force
Copy-Item -LiteralPath (Join-Path $projectRoot "README.md") -Destination (Join-Path $bundleDir "README.md") -Force

$versionInfo = Get-Content (Join-Path $projectRoot "app_version.json") -Raw | ConvertFrom-Json
$version = [string]$versionInfo.version
$zipName = "NOVA-INTERP-windows-x64-v$version.zip"
$zipPath = Join-Path $releaseDir $zipName
$hashPath = "$zipPath.sha256"

if (Test-Path $zipPath) {
  Remove-Item -LiteralPath $zipPath -Force
}
if (Test-Path $hashPath) {
  Remove-Item -LiteralPath $hashPath -Force
}

Compress-Archive -Path (Join-Path $bundleDir "*") -DestinationPath $zipPath -CompressionLevel Optimal

$hash = Get-FileHash -LiteralPath $zipPath -Algorithm SHA256
"$($hash.Hash.ToLowerInvariant())  $zipName" | Set-Content -Path $hashPath -Encoding ascii

Write-Host "Release bundle created:"
Write-Host "  $zipPath"
Write-Host "  $hashPath"
