# Utilidades comunes de backup (dot-sourcing). Requiere $AppRoot y $DataRoot definidos.
. (Join-Path $PSScriptRoot "..\lib.ps1")

$script:BackupRoot = Join-Path $DataRoot "backups"
$script:BackupLog = Join-Path $DataRoot ("logs\backup\backup-{0}.log" -f (Get-Date -Format "yyyy-MM"))

function Get-DbConnection([string]$DatabaseOverride) {
    $envValues = Read-EnvFile (Join-Path $AppRoot "backend\.env")
    if (-not $envValues["DATABASE_MIGRATION_URL"]) { throw "Falta DATABASE_MIGRATION_URL en backend\.env" }
    $conn = ConvertFrom-PgUrl $envValues["DATABASE_MIGRATION_URL"]
    if ($DatabaseOverride) { $conn.Database = $DatabaseOverride }
    return $conn
}

function Invoke-Pg([string]$Tool, [hashtable]$Conn, [string[]]$Arguments) {
    $exe = Find-PgTool $Tool
    $env:PGPASSWORD = $Conn.Password
    $env:PGCLIENTENCODING = "UTF8"
    $env:PGOPTIONS = "-c client_min_messages=warning"   # sin avisos informativos (NOTICE)
    # PS 5.1: con ErrorAction=Stop, cualquier línea en stderr de un programa nativo sería un error fatal.
    # El resultado se evalúa por el código de salida del programa.
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & $exe -h $Conn.Host -p $Conn.Port -U $Conn.User @Arguments 2>&1 | ForEach-Object { "$_" }
        $code = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previous
        Remove-Item Env:PGPASSWORD, Env:PGOPTIONS -ErrorAction SilentlyContinue
    }
    if ($code -ne 0) { throw "$Tool falló (código $code): $($output | Out-String)" }
    return $output
}

function Invoke-Sql([hashtable]$Conn, [string]$Sql) {
    return (Invoke-Pg "psql" $Conn @("-d", $Conn.Database, "-X", "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1", "-c", $Sql) | Out-String).Trim()
}

function Get-LatestDump([string]$Folder = "daily") {
    Get-ChildItem (Join-Path $BackupRoot $Folder) -Filter "*.dump" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
}

function Test-DumpChecksum([string]$Path) {
    $sumFile = "$Path.sha256"
    if (-not (Test-Path $sumFile)) { throw "No existe la suma de verificación $sumFile" }
    $expected = (Get-Content $sumFile -Raw).Trim().Split(" ")[0].ToLowerInvariant()
    $actual = (Get-FileHash -Algorithm SHA256 $Path).Hash.ToLowerInvariant()
    if ($expected -ne $actual) { throw "El archivo de backup está corrupto o fue alterado (SHA-256 no coincide): $Path" }
}

function Save-Status([string]$Name, [hashtable]$Data) {
    $Data["timestamp"] = (Get-Date).ToString("s")
    ($Data | ConvertTo-Json) | Set-Content -Path (Join-Path $BackupRoot "$Name.json") -Encoding UTF8
}
