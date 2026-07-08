$ErrorActionPreference = "Stop"

$envPath = Join-Path $PSScriptRoot "..\backend\.env"
if (-not (Test-Path $envPath)) {
  throw "Missing backend\.env. Copy backend\.env.example to backend\.env first."
}

$databaseUrlLine = Get-Content -LiteralPath $envPath | Where-Object { $_ -match "^DATABASE_URL=" } | Select-Object -First 1
if (-not $databaseUrlLine) {
  throw "DATABASE_URL not found in backend\.env."
}

$databaseUrl = ($databaseUrlLine -replace "^DATABASE_URL=", "").Trim()
if ($databaseUrl -notmatch "^postgresql(?:\+psycopg2)?://([^:]+):([^@]*)@([^:/]+):(\d+)/(.+)$") {
  throw "Unsupported DATABASE_URL format. Expected postgresql+psycopg2://user:password@host:port/database."
}

$dbUser = [System.Uri]::UnescapeDataString($Matches[1])
$dbPassword = [System.Uri]::UnescapeDataString($Matches[2])
$hostName = $Matches[3]
$port = $Matches[4]
$dbName = $Matches[5]

$env:PGPASSWORD = $dbPassword

$exists = & psql -h $hostName -p $port -U $dbUser -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$dbName'"
if ($exists -eq "1") {
  Write-Host "Database '$dbName' already exists."
} else {
  & psql -h $hostName -p $port -U $dbUser -d postgres -c "CREATE DATABASE $dbName"
  Write-Host "Database '$dbName' created."
}
