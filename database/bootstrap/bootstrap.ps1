<#
.SYNOPSIS
    Prepara PostgreSQL para el Sistema del Tópico CSJ Lima (roles, bases de datos, esquema).

.DESCRIPTION
    - Solicita la contraseña del superusuario de PostgreSQL (no se guarda).
    - Genera contraseñas aleatorias robustas para los roles topico_owner y topico_app.
    - Ejecuta bootstrap.sql para la base principal, la de verificación de backups y (opcional) la de pruebas.
    - Escribe/actualiza las cadenas de conexión en backend/.env (fuera del control de versiones).

    Es idempotente: re-ejecutarlo rota las contraseñas y actualiza backend/.env.

.EXAMPLE
    .\bootstrap.ps1
    .\bootstrap.ps1 -PgHost 10.10.1.20 -SkipTestDatabase
#>
[CmdletBinding()]
param(
    [string]$PgHost = "localhost",
    [int]$Port = 5432,
    [string]$SuperUser = "postgres",
    [string]$Database = "topico_csj",
    [string]$TestDatabase = "topico_csj_test",
    [string]$VerifyDatabase = "topico_csj_verify",
    [switch]$SkipTestDatabase,
    [string]$EnvFile = (Join-Path $PSScriptRoot "..\..\backend\.env")
)

$ErrorActionPreference = "Stop"

function New-RandomPassword([int]$Length = 32) {
    # Alfanumérico: no requiere escape en URLs de conexión.
    $chars = [char[]]"ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
    $bytes = New-Object byte[] $Length
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes)
    $rng.Dispose()
    -join ($bytes | ForEach-Object { $chars[$_ % $chars.Length] })
}

function Set-EnvValue([string[]]$Lines, [string]$Key, [string]$Value) {
    $pattern = "^\s*$([regex]::Escape($Key))\s*="
    $found = $false
    $result = foreach ($line in $Lines) {
        if ($line -match $pattern) { $found = $true; "$Key=$Value" } else { $line }
    }
    if (-not $found) { $result = @($result) + "$Key=$Value" }
    return ,$result
}

$psql = Get-Command psql -ErrorAction SilentlyContinue
if (-not $psql) {
    $candidate = Get-ChildItem "C:\Program Files\PostgreSQL\*\bin\psql.exe" -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending | Select-Object -First 1
    if (-not $candidate) { throw "No se encontró psql. Agregue el directorio bin de PostgreSQL al PATH." }
    $psqlPath = $candidate.FullName
} else {
    $psqlPath = $psql.Source
}

$secure = Read-Host "Contraseña del superusuario '$SuperUser' de PostgreSQL" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
$superPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)

$ownerPassword = New-RandomPassword
$appPassword = New-RandomPassword
$bootstrapSql = Join-Path $PSScriptRoot "bootstrap.sql"

# La base de verificación recibe restauraciones de prueba de los backups (verify-backup.ps1).
$databases = @($Database, $VerifyDatabase)
if (-not $SkipTestDatabase) { $databases += $TestDatabase }

try {
    $env:PGPASSWORD = $superPassword
    $env:TOPICO_OWNER_PASSWORD = $ownerPassword
    $env:TOPICO_APP_PASSWORD = $appPassword
    $env:PGCLIENTENCODING = "UTF8"

    foreach ($db in $databases) {
        Write-Host "==> Preparando base de datos '$db' en ${PgHost}:$Port" -ForegroundColor Cyan
        & $psqlPath -h $PgHost -p $Port -U $SuperUser -d postgres -X -q `
            -v ON_ERROR_STOP=1 -v "db_name=$db" -f $bootstrapSql
        if ($LASTEXITCODE -ne 0) { throw "psql terminó con código $LASTEXITCODE para '$db'." }
    }
}
finally {
    Remove-Item Env:PGPASSWORD, Env:TOPICO_OWNER_PASSWORD, Env:TOPICO_APP_PASSWORD -ErrorAction SilentlyContinue
    $superPassword = $null
}

# --- Actualiza backend/.env -------------------------------------------------
$EnvFile = [System.IO.Path]::GetFullPath($EnvFile)
$example = Join-Path (Split-Path $EnvFile) ".env.example"
if (Test-Path $EnvFile) {
    Copy-Item $EnvFile "$EnvFile.bak-$(Get-Date -Format yyyyMMddHHmmss)"
    $lines = Get-Content $EnvFile -Encoding UTF8
} elseif (Test-Path $example) {
    $lines = Get-Content $example -Encoding UTF8
} else {
    $lines = @()
}

$base = "postgresql+psycopg://{0}:{1}@${PgHost}:$Port/{2}"
$lines = Set-EnvValue $lines "DATABASE_URL" ($base -f "topico_app", $appPassword, $Database)
$lines = Set-EnvValue $lines "DATABASE_MIGRATION_URL" ($base -f "topico_owner", $ownerPassword, $Database)
if (-not $SkipTestDatabase) {
    $lines = Set-EnvValue $lines "TEST_DATABASE_URL" ($base -f "topico_app", $appPassword, $TestDatabase)
    $lines = Set-EnvValue $lines "TEST_DATABASE_MIGRATION_URL" ($base -f "topico_owner", $ownerPassword, $TestDatabase)
}
[System.IO.File]::WriteAllLines($EnvFile, $lines, (New-Object System.Text.UTF8Encoding $false))

Write-Host ""
Write-Host "Listo. Credenciales generadas y guardadas en: $EnvFile" -ForegroundColor Green
Write-Host "Siguiente paso:  cd backend; .\.venv\Scripts\alembic upgrade head"
