<#
.SYNOPSIS
    Publica una nueva versión del Tópico de Salud con un solo comando.

.DESCRIPTION
    1. Verifica que no haya cambios sin commit y que la versión sea nueva.
    2. Actualiza el número en backend/pyproject.toml, frontend/package.json y frontend/package-lock.json.
    3. Ejecuta las pruebas del backend y del frontend (se detiene si alguna falla).
    4. Hace commit, crea la etiqueta (v1.3 para 1.3.0; v1.3.1 para 1.3.1) y sube todo a GitHub.
    5. Publica en este servidor con update.ps1 y confirma la versión en /api/v1/health.

.EXAMPLE
    .\deploy\windows\nueva-version.ps1 -Version 1.4.0 -Mensaje "Reportes mensuales automáticos"
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Version,
    [string]$Mensaje = "",
    [switch]$SinPruebas,
    [switch]$SinPublicar
)
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here "lib.ps1")

$root = (Resolve-Path (Join-Path $here "..\..")).Path
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"

if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw "La versión debe tener el formato X.Y.Z (p. ej. 1.4.0)." }
$parts = $Version.Split(".")
$tag = if ($parts[2] -eq "0") { "v$($parts[0]).$($parts[1])" } else { "v$Version" }

Push-Location $root
try {
    Write-Step "Verificaciones previas"
    $pending = Invoke-Native { & git status --porcelain --untracked-files=no }
    if ($pending) { throw "Hay cambios sin commit. Haga commit (o descártelos) antes de publicar una versión:`n$($pending | Out-String)" }
    $existing = Invoke-Native { & git tag --list $tag }
    if ($existing) { throw "La etiqueta $tag ya existe: elija un número de versión nuevo." }
    $current = (Select-String -Path (Join-Path $backend "pyproject.toml") -Pattern '^version = "([^"]+)"').Matches[0].Groups[1].Value
    if ([version]$Version -le [version]$current) { throw "La versión $Version debe ser mayor que la actual ($current)." }
    Write-Ok "Versión actual $current → nueva $Version (etiqueta $tag)"

    Write-Step "Actualizando el número de versión"
    $pyproject = Join-Path $backend "pyproject.toml"
    $text = [IO.File]::ReadAllText($pyproject)
    $text = [regex]::Replace($text, '(?m)^version = "[^"]+"', "version = `"$Version`"", 1)
    [IO.File]::WriteAllText($pyproject, $text, (New-Object Text.UTF8Encoding($false)))
    # package.json y la raíz de package-lock.json (con node: conserva el formato JSON de npm)
    $js = "const fs=require('fs');for(const f of ['package.json','package-lock.json']){const j=JSON.parse(fs.readFileSync(f,'utf8'));j.version='$Version';if(j.packages&&j.packages[''])j.packages[''].version='$Version';fs.writeFileSync(f,JSON.stringify(j,null,2)+'\n');}"
    Push-Location $frontend
    try { Invoke-Native { & node -e $js } | Out-Null; if ($LASTEXITCODE -ne 0) { throw "No se pudo actualizar package.json" } } finally { Pop-Location }
    Write-Ok "backend/pyproject.toml, frontend/package.json y package-lock.json en $Version"

    if (-not $SinPruebas) {
        Write-Step "Pruebas del backend"
        Push-Location $backend
        $env:ENVIRONMENT = "development"
        try {
            $out = Invoke-Native { & .\.venv\Scripts\python -m pytest -q -p no:logging -rfE }
            $summary = ($out | Select-String -Pattern "passed|failed" | Select-Object -Last 1)
            if ($LASTEXITCODE -ne 0) {
                $out | Select-String -Pattern "^(FAILED|ERROR) |^E   " | Select-Object -First 30 | ForEach-Object { Write-Host "    $_" }
                throw "Fallaron pruebas del backend: $summary"
            }
            Write-Ok "$summary"
        } finally { Remove-Item Env:ENVIRONMENT -ErrorAction SilentlyContinue; Pop-Location }

        Write-Step "Pruebas del frontend"
        Push-Location $frontend
        try {
            $out = Invoke-Native { & npx vitest run }
            $summary = ($out | Select-String -CaseSensitive -Pattern "^\s*Tests\s" | Select-Object -Last 1)
            if ($LASTEXITCODE -ne 0) {
                $out | Select-String -Pattern "FAIL |AssertionError|Expected|Received" | Select-Object -First 30 | ForEach-Object { Write-Host "    $_" }
                throw "Fallaron pruebas del frontend: $summary"
            }
            Write-Ok "$("$summary".Trim())"
        } finally { Pop-Location }
    }

    Write-Step "Commit, etiqueta y subida a GitHub"
    $title = "Versión $Version" + $(if ($Mensaje) { ": $Mensaje" } else { "" })
    Invoke-Native { & git add backend/pyproject.toml frontend/package.json frontend/package-lock.json } | Out-Null
    $out = Invoke-Native { & git commit -q -m $title -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" }
    if ($LASTEXITCODE -ne 0) { throw "No se pudo hacer el commit: $($out | Out-String)" }
    $out = Invoke-Native { & git tag -a $tag -m $title }
    if ($LASTEXITCODE -ne 0) { throw "No se pudo crear la etiqueta: $($out | Out-String)" }
    $out = Invoke-Native { & git push -q origin main --tags }
    if ($LASTEXITCODE -ne 0) { throw "No se pudo subir a GitHub: $($out | Out-String)" }
    Write-Ok "$tag subido a GitHub ($((Invoke-Native { & git rev-parse --short HEAD }) | Select-Object -Last 1))"
} finally { Pop-Location }

if (-not $SinPublicar) {
    Write-Step "Publicando en este servidor"
    & (Join-Path $here "update.ps1")
    $health = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:42001/api/v1/health" -TimeoutSec 10
    if ($health.version -ne $Version) { throw "El servidor responde la versión $($health.version), se esperaba $Version." }
    Write-Ok "En producción: versión $($health.version)"
}
exit 0
