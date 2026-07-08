$ErrorActionPreference = "Stop"
$backend = Join-Path $PSScriptRoot "..\backend"
Set-Location $backend

$localPackages = Join-Path $backend ".python-packages"
if (Test-Path $localPackages) {
  $env:PYTHONPATH = $localPackages
}

python -m uvicorn app.main:app --reload
