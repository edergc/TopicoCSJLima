<#
.SYNOPSIS
    Diagnóstico rápido del Sistema del Tópico: servicios, puertos, salud, backups y espacio en disco.
#>
[CmdletBinding()]
param(
    [string]$AppRoot,
    [string]$DataRoot,
    [int]$WebPort = 42000,
    [int]$ApiPort = 42001
)

# (PS 5.1: $PSScriptRoot no está disponible en los valores por defecto de param)
if (-not $AppRoot) { $AppRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path }
if (-not $DataRoot) { $DataRoot = Join-Path (Split-Path $AppRoot) "TopicoCSJ-data" }

. (Join-Path $PSScriptRoot "lib.ps1")
$problems = 0
function Show([string]$Label, [bool]$Ok, [string]$Detail) {
    $mark = if ($Ok) { "[ OK ]" } else { "[FALLA]" }
    $color = if ($Ok) { "Green" } else { "Red" }
    Write-Host ("{0} {1,-28} {2}" -f $mark, $Label, $Detail) -ForegroundColor $color
    if (-not $Ok) { $script:problems++ }
}

Write-Host "Tópico de Salud CSJ Lima — estado ($(Get-Date -Format 'dd/MM/yyyy HH:mm'))" -ForegroundColor White
foreach ($name in $ServiceApi, $ServiceWeb, (Get-Service "postgresql*" | Select-Object -First 1).Name) {
    $svc = Get-Service $name -ErrorAction SilentlyContinue
    Show "Servicio $name" ($svc -and $svc.Status -eq "Running") $(if ($svc) { "$($svc.Status) · inicio $($svc.StartType)" } else { "no instalado" })
}

$api = Get-NetTCPConnection -State Listen -LocalPort $ApiPort -ErrorAction SilentlyContinue
Show "API en 127.0.0.1:$ApiPort" ($null -ne $api -and ($api.LocalAddress -notcontains "0.0.0.0")) $(if ($api) { "escuchando en $($api.LocalAddress -join ', ')" } else { "sin escuchar" })
$web = Get-NetTCPConnection -State Listen -LocalPort $WebPort -ErrorAction SilentlyContinue
Show "Web en puerto $WebPort" ($null -ne $web) $(if ($web) { "escuchando" } else { "sin escuchar" })

foreach ($scheme in "https", "http") {
    $ready = & curl.exe -sk --noproxy "*" --max-time 5 "${scheme}://localhost:$WebPort/api/v1/health/ready" 2>$null
    if ($ready) { break }
}
Show "Salud (vía proxy)" ("$ready" -match '"database":"ok"') "$ready"

$backups = Join-Path $DataRoot "backups"
foreach ($item in @(@("last-backup", "Último backup", 26), @("last-verify", "Última restauración de prueba", 24 * 8), @("last-audit-verify", "Última verificación auditoría", 26))) {
    $file = Join-Path $backups "$($item[0]).json"
    if (Test-Path $file) {
        $status = Get-Content $file -Raw | ConvertFrom-Json
        $age = ((Get-Date) - [datetime]$status.timestamp).TotalHours
        Show $item[1] ($status.result -eq "OK" -and $age -lt $item[2]) ("{0} · hace {1:N0} h {2}" -f $status.result, $age, $(if ($status.error) { "· $($status.error)" } else { "" }))
    } else {
        Show $item[1] $false "sin registros"
    }
}

$drive = Get-PSDrive (Split-Path $DataRoot -Qualifier).TrimEnd(":")
$freeGb = [math]::Round($drive.Free / 1GB, 1)
Show "Espacio libre ($($drive.Name):)" ($freeGb -gt 10) "$freeGb GB"

Write-Host ""
if ($problems -eq 0) { Write-Host "Todo en orden." -ForegroundColor Green } else { Write-Host "$problems punto(s) requieren atención. Logs: $(Join-Path $DataRoot 'logs')" -ForegroundColor Yellow }
exit $problems
