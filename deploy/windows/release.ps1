<#
.SYNOPSIS
    Publica una versión del código en la carpeta de PRODUCCIÓN y la despliega.

.DESCRIPTION
    El sistema en uso corre desde su propia carpeta (un "git worktree", por defecto
    E:\PROGRAMACION\TopicoCSJ-app), separada de la carpeta de desarrollo. Editar archivos o cambiar
    de rama en desarrollo NO afecta al sistema en uso: solo cambia cuando se ejecuta este script.

    1. Verifica que la carpeta de producción no tenga cambios locales (allí no se edita).
    2. La lleva a la versión indicada (por defecto, la rama main ya confirmada con commit).
    3. Ejecuta el update.ps1 de producción: backup, dependencias, migraciones, build y reinicio.

    Primera vez (crear la carpeta de producción): ver docs\05-despliegue.md, sección «Carpeta de producción».

.EXAMPLE
    .\deploy\windows\release.ps1              # publica main
    .\deploy\windows\release.ps1 -Ref 5b7b49e # publica (o vuelve a) un commit concreto
#>
[CmdletBinding()]
param(
    [string]$Ref = "main",
    [string]$ProdRoot = "E:\PROGRAMACION\TopicoCSJ-app",
    [switch]$SkipBackup
)
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here "lib.ps1")
Assert-Administrator

if (-not (Test-Path (Join-Path $ProdRoot ".git"))) {
    throw "No existe la carpeta de producción $ProdRoot. Créela primero (docs\05-despliegue.md, «Carpeta de producción»)."
}
$dirty = & git -C $ProdRoot status --porcelain --untracked-files=no
if ($dirty) { throw "La carpeta de producción tiene cambios locales (no se edita allí):`n$($dirty -join "`n")" }

$target = (& git -C $ProdRoot rev-parse --verify --quiet "$Ref^{commit}")
if (-not $target) { throw "No existe la versión '$Ref' (rama, etiqueta o commit)." }
$current = (& git -C $ProdRoot rev-parse HEAD)

Write-Step "Versión a publicar"
Write-Ok "Actual:  $(& git -C $ProdRoot log -1 --format='%h %s' $current)"
Write-Ok "Destino: $(& git -C $ProdRoot log -1 --format='%h %s' $target)"
& git -C $ProdRoot checkout --detach --quiet $target
if ($LASTEXITCODE -ne 0) { throw "No se pudo cambiar la carpeta de producción a $Ref." }

$update = Join-Path $ProdRoot "deploy\windows\update.ps1"
if ($SkipBackup) { & $update -SkipBackup } else { & $update }
