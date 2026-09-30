<#
.SYNOPSIS
    Retira los servicios, la regla de firewall y las tareas programadas del Tópico.

.DESCRIPTION
    NO elimina la base de datos, los backups, los logs ni el código: la desinstalación es reversible
    volviendo a ejecutar install.ps1.
#>
[CmdletBinding()]
param([string]$DataRoot)

# (PS 5.1: $PSScriptRoot no está disponible en los valores por defecto de param)
if (-not $DataRoot) { $DataRoot = Join-Path (Split-Path (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path) "TopicoCSJ-data" }

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "lib.ps1")
Assert-Administrator

foreach ($id in $ServiceWeb, $ServiceApi) {
    $wrapper = Join-Path $DataRoot "services\$id.exe"
    if (Get-Service $id -ErrorAction SilentlyContinue) {
        if (Test-Path $wrapper) {
            & $wrapper stop 2>&1 | Out-Null
            & $wrapper uninstall 2>&1 | Out-Null
        } else {
            Stop-Service $id -Force -ErrorAction SilentlyContinue
            & sc.exe delete $id | Out-Null
        }
        Write-Ok "Servicio $id retirado"
    }
}
Get-NetFirewallRule -DisplayName "TopicoCSJ Web*" -ErrorAction SilentlyContinue | Remove-NetFirewallRule
Write-Ok "Regla de firewall retirada"
Get-ScheduledTask -TaskName "$TaskPrefix - *" -ErrorAction SilentlyContinue | Unregister-ScheduledTask -Confirm:$false
Write-Ok "Tareas programadas retiradas"
Write-Host "Base de datos, backups y logs se conservan en $DataRoot." -ForegroundColor Yellow
