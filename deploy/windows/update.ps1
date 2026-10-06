<#
.SYNOPSIS
    Actualización rápida del Tópico de Salud en este servidor (código ya descargado con git pull).

.DESCRIPTION
    1. Backup de la base de datos.
    2. Dependencias del backend (si cambiaron) y migraciones (alembic upgrade head).
    3. Build del frontend y publicación en la carpeta web.
    4. Detención COMPLETA de los servicios del Tópico, incluidos procesos remanentes de uvicorn de
       despliegues anteriores (Restart-Service puede dejarlos vivos atendiendo con el código viejo).
       Solo se detienen procesos cuyo ejecutable es el entorno virtual de ESTE proyecto.
    5. Inicio de los servicios y verificación de salud.

    Para una instalación nueva o cambios de puertos/certificados use install.ps1.

.EXAMPLE
    git pull
    .\deploy\windows\update.ps1
#>
[CmdletBinding()]
param(
    [string]$DataDir = "E:\PROGRAMACION\TopicoCSJ-data",
    [int]$WebPort = 42000,
    [int]$ApiPort = 42001,
    [switch]$SkipBackup
)
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here "lib.ps1")
Assert-Administrator

$root = (Resolve-Path (Join-Path $here "..\..")).Path
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$python = Join-Path $backend ".venv\Scripts\python.exe"

if (-not $SkipBackup) {
    Write-Step "Backup previo"
    & (Join-Path $here "backup\backup.ps1") | Select-Object -Last 1
}

Write-Step "Dependencias del backend y migraciones"
Push-Location $backend
try {
    $out = Invoke-Native { & $python -m pip install --quiet --disable-pip-version-check -e . }
    if ($LASTEXITCODE -ne 0) { throw "Falló la instalación de dependencias: $($out | Out-String)" }
    $out = Invoke-Native { & $python -m alembic upgrade head }
    if ($LASTEXITCODE -ne 0) { throw "Falló la migración: $($out | Out-String)" }
    Write-Ok ($out | Select-Object -Last 1)
} finally { Pop-Location }

Write-Step "Build del frontend"
Push-Location $frontend
try {
    $out = Invoke-Native { & npm ci --no-audit --no-fund --loglevel=error }
    if ($LASTEXITCODE -ne 0) { throw "Falló 'npm ci': $($out | Out-String)" }
    $out = Invoke-Native { & npm run build }
    if ($LASTEXITCODE -ne 0) { throw "Falló el build: $($out | Out-String)" }
} finally { Pop-Location }
& robocopy (Join-Path $frontend "dist") (Join-Path $DataDir "web") /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "No se pudo publicar el frontend (robocopy $LASTEXITCODE)" }
Write-Ok "Frontend publicado en $(Join-Path $DataDir 'web')"

Write-Step "Reinicio completo de los servicios"
Stop-TopicoServices -Ports $ApiPort, $WebPort
$venvPattern = "*$backend\.venv*uvicorn*"
Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like $venvPattern } |
    ForEach-Object { Write-Warn "Proceso remanente $($_.ProcessId) detenido"; Stop-ProcessTree $_.ProcessId }
Start-Service $script:ServiceApi
Start-Service $script:ServiceWeb

$ok = $false
foreach ($i in 1..20) {
    Start-Sleep -Seconds 2
    try {
        $r = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$ApiPort/api/v1/health" -TimeoutSec 5
        if ($r.StatusCode -eq 200) { $ok = $true; break }
    } catch { }
}
if (-not $ok) { throw "La API no respondió tras el reinicio. Revise $DataDir\logs\api" }
Write-Ok "Actualización completa. Sistema en http://<servidor>:$WebPort"

exit 0
