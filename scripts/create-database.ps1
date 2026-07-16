param(
    [string]$DatabaseName = "ai_tour_guide",
    [string]$HostName = "localhost",
    [int]$Port = 5432,
    [string]$Username = "postgres",
    [string]$Password = $env:PGPASSWORD
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command psql -ErrorAction SilentlyContinue)) {
    throw "psql was not found. Install PostgreSQL client tools or add psql to PATH."
}

if ([string]::IsNullOrWhiteSpace($Password)) {
    $securePassword = Read-Host "PostgreSQL password for $Username" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
    try {
        $Password = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

if ($DatabaseName -notmatch '^[A-Za-z_][A-Za-z0-9_]*$') {
    throw "DatabaseName must contain only letters, numbers, and underscores, and cannot start with a number."
}

$env:PGPASSWORD = $Password
try {
    $exists = & psql -w -h $HostName -p $Port -U $Username -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$DatabaseName'"
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to connect to PostgreSQL as '$Username' on ${HostName}:$Port."
    }

    if ($null -ne $exists -and $exists.Trim() -eq "1") {
        Write-Host "Database '$DatabaseName' already exists."
        exit 0
    }

    & psql -w -h $HostName -p $Port -U $Username -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE $DatabaseName"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create database '$DatabaseName'."
    }

    Write-Host "Database '$DatabaseName' created."
} finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
}
