$ErrorActionPreference = "Stop"
$backend = Join-Path $PSScriptRoot "..\backend"
Set-Location $backend

$localPackages = Join-Path $backend ".python-packages"
if (Test-Path $localPackages) {
  $env:PYTHONPATH = $localPackages
}
$env:PYTHONUNBUFFERED = "1"

python -m app.workers.insight_report_scheduler
