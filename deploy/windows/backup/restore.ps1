<#
.SYNOPSIS
    Restaura la base del Tópico desde un backup. OPERACIÓN CRÍTICA.

.DESCRIPTION
    1. Valida la suma SHA-256 del archivo.
    2. Detiene los servicios (nadie escribe durante la restauración).
    3. Toma un backup de SEGURIDAD del estado actual (backups\pre-restore).
    4. Reemplaza el esquema "topico" con el contenido del backup (en una sola transacción).
    5. Aplica migraciones pendientes (si el backup es de una versión anterior) y verifica la auditoría.
    6. Inicia los servicios.
    Exige escribir una confirmación explícita.

.EXAMPLE
    .\restore.ps1 -DumpFile E:\PROGRAMACION\TopicoCSJ-data\backups\daily\topico_csj_20260929_220000.dump
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$DumpFile,
    [switch]$Force,
    [string]$AppRoot,
    [string]$DataRoot
)

# (PS 5.1: $PSScriptRoot no está disponible en los valores por defecto de param)
if (-not $AppRoot) { $AppRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path }
if (-not $DataRoot) { $DataRoot = Join-Path (Split-Path $AppRoot) "TopicoCSJ-data" }

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common.ps1")
Assert-Administrator

$conn = Get-DbConnection
$DumpFile = (Resolve-Path $DumpFile).Path
Test-DumpChecksum $DumpFile

Write-Host ""
Write-Host "RESTAURACIÓN DE BASE DE DATOS" -ForegroundColor Red
Write-Host "  Base de datos: $($conn.Database) en $($conn.Host):$($conn.Port)"
Write-Host "  Backup:        $DumpFile ($((Get-Item $DumpFile).LastWriteTime))"
Write-Host "  Los datos actuales serán REEMPLAZADOS (se guardará antes un backup de seguridad)."
if (-not $Force) {
    $typed = Read-Host "Para continuar escriba exactamente: RESTAURAR $($conn.Database)"
    if ($typed -ne "RESTAURAR $($conn.Database)") { Write-Host "Cancelado."; exit 1 }
}

$services = @($ServiceWeb, $ServiceApi) | Where-Object { Get-Service $_ -ErrorAction SilentlyContinue }
try {
    Write-Log $BackupLog "RESTAURACIÓN iniciada desde $DumpFile"
    foreach ($svc in $services) { Stop-Service $svc -Force; Write-Log $BackupLog "Servicio detenido: $svc" }

    & (Join-Path $PSScriptRoot "backup.ps1") -AppRoot $AppRoot -DataRoot $DataRoot -Folder "pre-restore"
    if ($LASTEXITCODE -ne 0) { throw "No se pudo tomar el backup de seguridad; restauración abortada (no se modificó nada)." }

    # El esquema actual se APARTA (no se borra): si la restauración falla, se devuelve a su lugar.
    $parked = "topico_prev_" + (Get-Date -Format "yyyyMMddHHmmss")
    Invoke-Sql $conn "ALTER SCHEMA topico RENAME TO $parked" | Out-Null
    try {
        Invoke-Pg "pg_restore" $conn @("-d", $conn.Database, "--no-owner", "--role=$($conn.User)", "--exit-on-error", "--single-transaction", $DumpFile) | Out-Null
    }
    catch {
        Invoke-Sql $conn "DROP SCHEMA IF EXISTS topico CASCADE; ALTER SCHEMA $parked RENAME TO topico" | Out-Null
        Write-Log $BackupLog "pg_restore falló; se devolvió el esquema original a su lugar (sin cambios en los datos)"
        throw
    }
    Invoke-Sql $conn "DROP SCHEMA $parked CASCADE" | Out-Null
    Write-Log $BackupLog "Datos restaurados"

    Push-Location (Join-Path $AppRoot "backend")
    try {
        $python = Join-Path $AppRoot "backend\.venv\Scripts\python.exe"
        $out = Invoke-Native { & $python -m alembic upgrade head }
        if ($LASTEXITCODE -ne 0) { throw "Falló la actualización del esquema tras la restauración: $($out | Out-String)" }
    }
    finally { Pop-Location }
    $problems = [int](Invoke-Sql $conn "SELECT count(*) FROM topico.verify_audit_chain()")
    Write-Log $BackupLog "Verificación de auditoría tras restaurar: $(if ($problems -eq 0) { 'íntegra' } else { "$problems problema(s)" })"
}
catch {
    Write-Log $BackupLog "ERROR EN LA RESTAURACIÓN: $($_.Exception.Message)"
    Write-Host "El backup de seguridad previo está en: $(Join-Path $BackupRoot 'pre-restore')" -ForegroundColor Yellow
    throw
}
finally {
    foreach ($svc in @($ServiceApi, $ServiceWeb)) {
        if (Get-Service $svc -ErrorAction SilentlyContinue) { Start-Service $svc; Write-Log $BackupLog "Servicio iniciado: $svc" }
    }
}
Write-Host "Restauración completada." -ForegroundColor Green
