<#
.SYNOPSIS
    Verifica que el último backup SE PUEDE RESTAURAR (restauración de prueba en una base aislada).

.DESCRIPTION
    Un backup que nunca se restauró no es un backup. Semanalmente:
      1. Valida la suma SHA-256 del archivo.
      2. Lo restaura en la base de verificación (por defecto topico_csj_verify; nunca en producción).
      3. Comprueba: versión del esquema, conteos básicos e integridad de la cadena de auditoría.
    Deja backups\last-verify.json para el diagnóstico (status.ps1).
#>
[CmdletBinding()]
param(
    [string]$AppRoot,
    [string]$DataRoot,
    [string]$DumpFile,
    [string]$VerifyDatabase = "topico_csj_verify"
)

# (PS 5.1: $PSScriptRoot no está disponible en los valores por defecto de param)
if (-not $AppRoot) { $AppRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path }
if (-not $DataRoot) { $DataRoot = Join-Path (Split-Path $AppRoot) "TopicoCSJ-data" }

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common.ps1")

try {
    $source = Get-DbConnection
    if ($VerifyDatabase -eq $source.Database) { throw "La base de verificación no puede ser la base de producción." }
    $conn = Get-DbConnection -DatabaseOverride $VerifyDatabase
    if (-not $DumpFile) {
        $latest = Get-LatestDump
        if (-not $latest) { throw "No hay backups para verificar." }
        $DumpFile = $latest.FullName
    }
    Write-Log $BackupLog "Verificación de restauración: $DumpFile → $VerifyDatabase"
    Test-DumpChecksum $DumpFile

    Invoke-Sql $conn "DROP SCHEMA IF EXISTS topico CASCADE" | Out-Null
    Invoke-Pg "pg_restore" $conn @("-d", $VerifyDatabase, "--no-owner", "--role=$($conn.User)", "--exit-on-error", "--single-transaction", $DumpFile) | Out-Null

    $revision = Invoke-Sql $conn "SELECT version_num FROM topico.alembic_version"
    # Solo ASCII en los argumentos: PS 5.1 los envía en la codificación ANSI de la consola.
    $n = (Invoke-Sql $conn "SELECT (SELECT count(*) FROM topico.appointment) || '|' || (SELECT count(*) FROM topico.worker) || '|' || (SELECT count(*) FROM topico.audit_event)").Split("|")
    $counts = "$($n[0]) atenciones, $($n[1]) trabajadores, $($n[2]) eventos de auditoría"
    $problems = [int](Invoke-Sql $conn "SELECT count(*) FROM topico.verify_audit_chain()")
    if ($problems -gt 0) { throw "La auditoría restaurada presenta $problems problema(s) de integridad." }

    Invoke-Sql $conn "DROP SCHEMA IF EXISTS topico CASCADE" | Out-Null   # no se conservan datos personales en la copia de prueba
    Write-Log $BackupLog "Restauración verificada: esquema $revision; $counts; auditoría íntegra"
    Save-Status "last-verify" @{ result = "OK"; file = $DumpFile; revision = $revision; summary = $counts }
    exit 0
}
catch {
    Write-Log $BackupLog "ERROR en la verificación: $($_.Exception.Message)"
    Save-Status "last-verify" @{ result = "ERROR"; file = $DumpFile; error = $_.Exception.Message }
    exit 1
}
