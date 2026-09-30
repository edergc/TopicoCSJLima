<#
.SYNOPSIS
    Verificación diaria de la integridad de la auditoría (cadena de hash). Código de salida 2 = alteración detectada.
#>
[CmdletBinding()]
param(
    [string]$AppRoot,
    [string]$DataRoot
)

# (PS 5.1: $PSScriptRoot no está disponible en los valores por defecto de param)
if (-not $AppRoot) { $AppRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path }
if (-not $DataRoot) { $DataRoot = Join-Path (Split-Path $AppRoot) "TopicoCSJ-data" }

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common.ps1")
$log = Join-Path $DataRoot ("logs\backup\audit-{0}.log" -f (Get-Date -Format "yyyy-MM"))
$python = Join-Path $AppRoot "backend\.venv\Scripts\python.exe"

Push-Location (Join-Path $AppRoot "backend")
try {
    $env:PYTHONUTF8 = "1"
    $output = Invoke-Native { & $python -m app.cli verify-audit } | Out-String
    $code = $LASTEXITCODE
}
finally { Pop-Location }
Write-Log $log ("[{0}] {1}" -f $(if ($code -eq 0) { "OK" } else { "ALERTA" }), $output.Trim())
Save-Status "last-audit-verify" @{ result = $(if ($code -eq 0) { "OK" } else { "ALERTA" }); output = $output.Trim() }
exit $code
