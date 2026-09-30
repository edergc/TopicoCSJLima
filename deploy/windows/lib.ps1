# Funciones compartidas por los scripts de despliegue (se carga con dot-sourcing).

$script:ToolHashes = @{
    "caddy.exe"     = "5cb9ab71e5756ce72840b8234177a2f40c8b4ab47a806b8e841e2b784e9df62b"  # Caddy v2.11.4 windows/amd64
    "WinSW-x64.exe" = "05b82d46ad331cc16bdc00de5c6332c1ef818df8ceefcd49c726553209b3a0da"  # WinSW v2.12.0
}

$script:ServiceApi = "TopicoCSJ-API"
$script:ServiceWeb = "TopicoCSJ-Web"
$script:TaskPrefix = "TopicoCSJ"

function Invoke-Native([scriptblock]$Block) {
    <# Ejecuta un programa externo capturando stdout+stderr como texto. En Windows PowerShell 5.1,
       con ErrorAction=Stop, cualquier línea en stderr sería un error fatal aunque el programa
       termine bien; aquí se decide por $LASTEXITCODE. #>
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try { return (& $Block 2>&1 | ForEach-Object { "$_" }) }
    finally { $ErrorActionPreference = $previous }
}

function Write-Step([string]$Message) { Write-Host "==> $Message" -ForegroundColor Cyan }
function Write-Ok([string]$Message) { Write-Host "    OK  $Message" -ForegroundColor Green }
function Write-Warn([string]$Message) { Write-Host "    AVISO  $Message" -ForegroundColor Yellow }

function Test-ToolHash([string]$Path) {
    $name = Split-Path $Path -Leaf
    $expected = $script:ToolHashes[$name]
    if (-not $expected) { return $false }
    return (Get-FileHash -Algorithm SHA256 -Path $Path).Hash.ToLowerInvariant() -eq $expected
}

function Assert-Administrator {
    $principal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Ejecute este script en una consola de PowerShell 'Como administrador'."
    }
}

function Read-EnvFile([string]$Path) {
    $values = @{}
    if (-not (Test-Path $Path)) { return $values }
    foreach ($line in Get-Content $Path -Encoding UTF8) {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$') { $values[$Matches[1]] = $Matches[2].Trim() }
    }
    return $values
}

function Set-EnvValues([string]$Path, [hashtable]$Values, [string[]]$Remove = @()) {
    $lines = if (Test-Path $Path) { @(Get-Content $Path -Encoding UTF8) } else { @() }
    $pending = @{} + $Values
    $result = foreach ($line in $lines) {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=') {
            $key = $Matches[1]
            if ($Remove -contains $key) { continue }
            if ($pending.ContainsKey($key)) { "$key=$($pending[$key])"; $pending.Remove($key); continue }
        }
        $line
    }
    foreach ($key in $pending.Keys) { $result = @($result) + "$key=$($pending[$key])" }
    [IO.File]::WriteAllLines($Path, [string[]]$result, (New-Object Text.UTF8Encoding $false))
}

function ConvertFrom-PgUrl([string]$Url) {
    # postgresql+psycopg://usuario:clave@host:puerto/bd
    if ($Url -notmatch '^postgresql(\+psycopg)?://([^:]+):([^@]*)@([^:/]+):?(\d*)/(.+)$') {
        throw "URL de base de datos no reconocida."
    }
    return @{
        User = [Uri]::UnescapeDataString($Matches[2]); Password = [Uri]::UnescapeDataString($Matches[3])
        Host = $Matches[4]; Port = $(if ($Matches[5]) { $Matches[5] } else { "5432" }); Database = $Matches[6]
    }
}

function Find-PgTool([string]$Name) {
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $candidate = Get-ChildItem "C:\Program Files\PostgreSQL\*\bin\$Name.exe" -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending | Select-Object -First 1
    if (-not $candidate) { throw "No se encontró $Name. Agregue el directorio bin de PostgreSQL al PATH." }
    return $candidate.FullName
}

function New-RandomSecret([int]$Length = 64) {
    $bytes = New-Object byte[] $Length
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes); $rng.Dispose()
    return ([Convert]::ToBase64String($bytes) -replace '[+/=]', '').Substring(0, $Length)
}

function Write-Log([string]$File, [string]$Message) {
    $dir = Split-Path $File
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    $line = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Path $File -Value $line -Encoding UTF8
    Write-Host $line
}

function Stop-ProcessTree([int]$ProcessId) {
    Get-CimInstance Win32_Process -Filter "ParentProcessId=$ProcessId" -ErrorAction SilentlyContinue |
        ForEach-Object { Stop-ProcessTree $_.ProcessId }
    Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
}

function Stop-TopicoServices([int[]]$Ports) {
    <# Detiene los servicios del Tópico y elimina procesos remanentes de SU propio árbol
       (envoltorios WinSW, uvicorn y sus workers, Caddy) que sigan ocupando los puertos del sistema.
       Nunca toca procesos de otras aplicaciones: solo python/caddy/envoltorios TopicoCSJ. #>
    foreach ($id in $script:ServiceWeb, $script:ServiceApi) {
        $svc = Get-Service $id -ErrorAction SilentlyContinue
        if ($svc -and $svc.Status -ne "Stopped") {
            Stop-Service $id -Force -ErrorAction SilentlyContinue
            try { $svc.WaitForStatus("Stopped", [TimeSpan]::FromSeconds(45)) } catch { }
        }
    }
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -in "$($script:ServiceApi).exe", "$($script:ServiceWeb).exe" } |
        ForEach-Object { Stop-ProcessTree $_.ProcessId }
    foreach ($port in $Ports) {
        Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue | ForEach-Object {
            $ownerId = $_.OwningProcess
            $owner = Get-Process -Id $ownerId -ErrorAction SilentlyContinue
            if ($owner) {
                if ($owner.ProcessName -in "python", "caddy") { Stop-ProcessTree $ownerId }
            } else {
                # Windows reporta como dueño a un proceso ya terminado: el socket lo retienen sus hijos
                # (workers de uvicorn que heredaron el socket).
                Get-CimInstance Win32_Process -Filter "ParentProcessId=$ownerId" -ErrorAction SilentlyContinue |
                    Where-Object { $_.Name -in "python.exe", "caddy.exe" } |
                    ForEach-Object { Stop-ProcessTree $_.ProcessId }
            }
        }
    }
    Start-Sleep -Seconds 2
}
