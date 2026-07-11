$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$backendEnvPath = Join-Path $projectRoot "backend\.env"
$backendDockerEnvPath = Join-Path $projectRoot "backend\.env.docker"
$dataDirectory = Join-Path $projectRoot ".local-data\pgvector-postgres"

if (-not (Test-Path -LiteralPath $backendEnvPath)) {
  throw "Missing backend\.env. Copy backend\.env.example first."
}

$databaseUrlLine = Get-Content -LiteralPath $backendEnvPath -Encoding utf8 |
  Where-Object { $_ -match "^DATABASE_URL=" } |
  Select-Object -First 1

if (-not $databaseUrlLine) {
  throw "DATABASE_URL not found in backend\.env."
}

$databaseUrl = ($databaseUrlLine -replace "^DATABASE_URL=", "").Trim()
if ($databaseUrl -notmatch "^postgresql(?:\+psycopg2)?://([^:]+):([^@]*)@([^:/]+):(\d+)/([^?]+)$") {
  throw "Unsupported DATABASE_URL format. Expected postgresql+psycopg2://user:password@localhost:port/database."
}

$dbUser = [System.Uri]::UnescapeDataString($Matches[1])
$dbPassword = [System.Uri]::UnescapeDataString($Matches[2])
$dbHost = $Matches[3]
$dbPort = [int]$Matches[4]
$dbName = $Matches[5]

if ($dbHost -notin @("localhost", "127.0.0.1")) {
  throw "Docker pgvector only supports a local DATABASE_URL. Current host: $dbHost"
}

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$existingBinding = docker port ai-tour-guide-postgres 5432/tcp 2>$null | Select-Object -First 1
$dockerPortExitCode = $LASTEXITCODE
$ErrorActionPreference = $previousErrorActionPreference
if ($dockerPortExitCode -ne 0) {
  # Docker returns exit code 1 when a pre-existing container is stopped. That is
  # expected after Docker Desktop restarts; compose up below will restore it.
  $existingBinding = $null
}
if ($existingBinding -match ":(\d+)$") {
  $selectedPort = [int]$Matches[1]
} else {
  $selectedPort = $dbPort
  $listener = Get-NetTCPConnection -LocalPort $selectedPort -State Listen -ErrorAction SilentlyContinue
  if ($listener) {
    $selectedPort = 5433..5450 | Where-Object {
      -not (Get-NetTCPConnection -LocalPort $_ -State Listen -ErrorAction SilentlyContinue)
    } | Select-Object -First 1

    if (-not $selectedPort) {
      throw "No free port found in the 5433-5450 range for the pgvector PostgreSQL container."
    }
  }
}

New-Item -ItemType Directory -Force -Path $dataDirectory | Out-Null
[System.IO.File]::WriteAllText(
  $backendDockerEnvPath,
  "DATABASE_PORT_OVERRIDE=$selectedPort`n",
  [System.Text.UTF8Encoding]::new($false)
)

$env:POSTGRES_USER = $dbUser
$env:POSTGRES_PASSWORD = $dbPassword
$env:POSTGRES_DB = $dbName
$env:POSTGRES_HOST_PORT = $selectedPort.ToString()
$env:POSTGRES_DATA_DIR = $dataDirectory

try {
  docker compose --project-directory $projectRoot up -d
  for ($attempt = 1; $attempt -le 30; $attempt++) {
    $health = docker inspect --format '{{.State.Health.Status}}' ai-tour-guide-postgres 2>$null
    if ($health -eq "healthy") {
      $quotedUser = '"' + $dbUser.Replace('"', '""') + '"'
      $passwordLiteral = $dbPassword.Replace("'", "''")
      $passwordQuery = "ALTER ROLE $quotedUser PASSWORD '$passwordLiteral';"
      docker exec ai-tour-guide-postgres psql -v ON_ERROR_STOP=1 -U $dbUser -d $dbName -c $passwordQuery | Out-Null
      if ($LASTEXITCODE -ne 0) {
        throw "Unable to synchronize the pgvector PostgreSQL password with backend\.env."
      }
      Write-Host "pgvector PostgreSQL is ready on localhost:$selectedPort."
      exit 0
    }
    Start-Sleep -Seconds 2
  }
  throw "The pgvector PostgreSQL container did not become healthy in time."
} finally {
  Remove-Item Env:POSTGRES_USER -ErrorAction SilentlyContinue
  Remove-Item Env:POSTGRES_PASSWORD -ErrorAction SilentlyContinue
  Remove-Item Env:POSTGRES_DB -ErrorAction SilentlyContinue
  Remove-Item Env:POSTGRES_HOST_PORT -ErrorAction SilentlyContinue
  Remove-Item Env:POSTGRES_DATA_DIR -ErrorAction SilentlyContinue
}
