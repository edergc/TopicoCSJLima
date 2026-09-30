<#
.SYNOPSIS
    Backup completo de la base del Tópico (pg_dump formato custom) con retención y verificación.

.DESCRIPTION
    - Respaldo del esquema "topico" (datos + estructura + privilegios) en formato custom comprimido.
    - Suma SHA-256 junto a cada archivo; se valida que el archivo sea legible (pg_restore --list).
    - Retención: diarios (14), semanales (domingo, 8), mensuales (primer backup del mes, 12).
    - Copia opcional a un segundo destino (otro disco o carpeta de red): -SecondaryPath.
    Registra en logs\backup\ y deja backups\last-backup.json para el diagnóstico (status.ps1).

    Programado por install.ps1 como tarea diaria. Ejecución manual:
        .\backup.ps1 -DataRoot E:\PROGRAMACION\TopicoCSJ-data
#>
[CmdletBinding()]
param(
    [string]$AppRoot,
    [string]$DataRoot,
    [int]$KeepDaily = 14,
    [int]$KeepWeekly = 8,
    [int]$KeepMonthly = 12,
    [string]$SecondaryPath,
    [string]$Folder = "daily"
)

# (PS 5.1: $PSScriptRoot no está disponible en los valores por defecto de param)
if (-not $AppRoot) { $AppRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path }
if (-not $DataRoot) { $DataRoot = Join-Path (Split-Path $AppRoot) "TopicoCSJ-data" }

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common.ps1")

try {
    $conn = Get-DbConnection
    foreach ($f in "daily", "weekly", "monthly", $Folder) { New-Item -ItemType Directory -Force -Path (Join-Path $BackupRoot $f) | Out-Null }
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $file = Join-Path $BackupRoot "$Folder\$($conn.Database)_$stamp.dump"
    Write-Log $BackupLog "Inicio de backup de '$($conn.Database)' → $file"

    Invoke-Pg "pg_dump" $conn @("-d", $conn.Database, "--schema=topico", "--format=custom", "--compress=6", "--file=$file") | Out-Null
    Invoke-Pg "pg_restore" $conn @("--list", $file) | Out-Null   # el archivo es legible y consistente
    $hash = (Get-FileHash -Algorithm SHA256 $file).Hash.ToLowerInvariant()
    "$hash  $(Split-Path $file -Leaf)" | Set-Content -Path "$file.sha256" -Encoding ASCII
    $sizeMb = [math]::Round((Get-Item $file).Length / 1MB, 2)
    Write-Log $BackupLog "Backup creado ($sizeMb MB, SHA-256 $($hash.Substring(0, 16))…)"

    if ($Folder -eq "daily") {
        $today = Get-Date
        $monthTag = $today.ToString("yyyyMM")
        $copies = @()
        if ($today.DayOfWeek -eq "Sunday") { $copies += "weekly" }
        if (-not (Get-ChildItem (Join-Path $BackupRoot "monthly") -Filter "*_$monthTag*.dump" -ErrorAction SilentlyContinue)) { $copies += "monthly" }
        foreach ($target in $copies) {
            Copy-Item $file, "$file.sha256" -Destination (Join-Path $BackupRoot $target)
            Write-Log $BackupLog "Copia $target conservada"
        }
        foreach ($rule in @(@("daily", $KeepDaily), @("weekly", $KeepWeekly), @("monthly", $KeepMonthly))) {
            $old = Get-ChildItem (Join-Path $BackupRoot $rule[0]) -Filter "*.dump" | Sort-Object LastWriteTime -Descending | Select-Object -Skip $rule[1]
            foreach ($item in $old) {
                Remove-Item $item.FullName, "$($item.FullName).sha256" -Force -ErrorAction SilentlyContinue
                Write-Log $BackupLog "Retención: eliminado $($rule[0])\$($item.Name)"
            }
        }
    }

    if ($SecondaryPath) {
        New-Item -ItemType Directory -Force -Path $SecondaryPath | Out-Null
        Copy-Item $file, "$file.sha256" -Destination $SecondaryPath
        Write-Log $BackupLog "Copia secundaria en $SecondaryPath"
    }

    Save-Status "last-backup" @{ result = "OK"; file = $file; size_mb = $sizeMb; sha256 = $hash }
    Write-Log $BackupLog "Backup finalizado correctamente"
    exit 0
}
catch {
    Write-Log $BackupLog "ERROR: $($_.Exception.Message)"
    if (Test-Path $BackupRoot) { Save-Status "last-backup" @{ result = "ERROR"; error = $_.Exception.Message } }
    exit 1
}
