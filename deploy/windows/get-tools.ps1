<#
.SYNOPSIS
    Descarga las herramientas de despliegue (Caddy y WinSW) y verifica su integridad.

.DESCRIPTION
    Solo acepta binarios cuyo SHA-256 coincide con el valor fijado aquí (defensa ante descargas
    alteradas). En servidores SIN Internet: descargue ambos archivos en otro equipo, verifique el
    SHA-256 y cópielos a deploy\windows\bin\ ; install.ps1 los validará igualmente.

    - Caddy v2.11.4 (proxy inverso + HTTPS): verificado contra caddy_2.11.4_checksums.txt (SHA-512)
    - WinSW v2.12.0 (envoltorio de servicios de Windows)
#>
[CmdletBinding()]
param([string]$BinDir)

# (PS 5.1: $PSScriptRoot no está disponible en los valores por defecto de param)
if (-not $BinDir) { $BinDir = Join-Path $PSScriptRoot "bin" }

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "lib.ps1")

$tools = @(
    @{ Name = "caddy.exe";     Url = "https://github.com/caddyserver/caddy/releases/download/v2.11.4/caddy_2.11.4_windows_amd64.zip"; Zip = $true },
    @{ Name = "WinSW-x64.exe"; Url = "https://github.com/winsw/winsw/releases/download/v2.12.0/WinSW-x64.exe"; Zip = $false }
)

New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

foreach ($tool in $tools) {
    $target = Join-Path $BinDir $tool.Name
    if ((Test-Path $target) -and (Test-ToolHash $target)) {
        Write-Step "$($tool.Name) ya presente y verificado."
        continue
    }
    Write-Step "Descargando $($tool.Name)…"
    $tmp = Join-Path $env:TEMP ([IO.Path]::GetRandomFileName())
    Invoke-WebRequest -Uri $tool.Url -OutFile $tmp -UseBasicParsing
    if ($tool.Zip) {
        $extract = "$tmp-dir"
        Expand-Archive -Path $tmp -DestinationPath $extract -Force
        Move-Item (Join-Path $extract $tool.Name) $target -Force
        Remove-Item $extract -Recurse -Force
        Remove-Item $tmp -Force
    } else {
        Move-Item $tmp $target -Force
    }
    if (-not (Test-ToolHash $target)) {
        Remove-Item $target -Force
        throw "El SHA-256 de $($tool.Name) no coincide con el valor esperado. Descarga rechazada."
    }
    Write-Ok "$($tool.Name) descargado y verificado."
}
