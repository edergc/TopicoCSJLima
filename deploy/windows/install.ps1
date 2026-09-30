<#
.SYNOPSIS
    Instala o actualiza el Sistema del Tópico de Salud CSJ Lima en Windows Server.

.DESCRIPTION
    Idempotente: úselo para la primera instalación y para cada actualización (tras "git pull").

      Usuarios (LAN) ──HTTPS:42000──> Caddy (servicio TopicoCSJ-Web)
                                         ├─ /        → frontend (archivos estáticos)
                                         └─ /api/*   → 127.0.0.1:42001 (servicio TopicoCSJ-API, FastAPI)
                                                          └─ PostgreSQL (topico_csj)

    Solo el puerto web queda abierto en el firewall; la API escucha únicamente en 127.0.0.1.

    Requisitos previos (una sola vez): PostgreSQL 16 y database\bootstrap\bootstrap.ps1 ejecutado
    (crea roles, bases de datos y backend\.env).

.EXAMPLE
    .\install.ps1
    .\install.ps1 -HostNames topico.csjlima.gob.pe -TlsMode files -CertFile C:\certs\topico.crt -KeyFile C:\certs\topico.key
    .\install.ps1 -SkipFrontendBuild      # actualización solo del backend
#>
[CmdletBinding()]
param(
    [string]$AppRoot,
    [string]$DataRoot,
    [int]$WebPort = 42000,
    [int]$ApiPort = 42001,
    [ValidateSet("internal", "files", "none")][string]$TlsMode = "internal",
    [string[]]$HostNames,
    [string]$CertFile,
    [string]$KeyFile,
    [ValidateSet("auto", "LocalService", "LocalSystem")][string]$ServiceAccount = "auto",
    [ValidateRange(1, 8)][int]$Workers = 2,
    [string]$BackupTime = "22:00",
    [switch]$SkipFrontendBuild,
    [switch]$SkipFirewall,
    [switch]$SkipTasks,
    [switch]$SkipServices
)

# (PS 5.1: $PSScriptRoot no está disponible en los valores por defecto de param)
if (-not $AppRoot) { $AppRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path }
if (-not $DataRoot) { $DataRoot = Join-Path (Split-Path $AppRoot) "TopicoCSJ-data" }

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "lib.ps1")
Assert-Administrator

$BackendDir = Join-Path $AppRoot "backend"
$FrontendDir = Join-Path $AppRoot "frontend"
$EnvFile = Join-Path $BackendDir ".env"
$VenvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"
$BinDir = Join-Path $PSScriptRoot "bin"
$Dirs = @{
    Root = $DataRoot; Web = Join-Path $DataRoot "web"; Services = Join-Path $DataRoot "services"
    Caddy = Join-Path $DataRoot "caddy"; Logs = Join-Path $DataRoot "logs"; Backups = Join-Path $DataRoot "backups"
}

Write-Host ""
Write-Host "Tópico de Salud CSJ Lima — instalación" -ForegroundColor White
Write-Host "  Aplicación: $AppRoot"
Write-Host "  Datos:      $DataRoot"
Write-Host "  Puertos:    web $WebPort (LAN) · API $ApiPort (solo 127.0.0.1)"
Write-Host ""

# ----------------------------------------------------------------------------- 1. Prerrequisitos
Write-Step "Verificando prerrequisitos"
if (-not (Test-Path $EnvFile)) {
    throw "No existe backend\.env. Ejecute primero database\bootstrap\bootstrap.ps1."
}
$envValues = Read-EnvFile $EnvFile
foreach ($key in "DATABASE_URL", "DATABASE_MIGRATION_URL") {
    if (-not $envValues[$key] -or $envValues[$key] -match "CAMBIAR") { throw "Falta $key en backend\.env (ejecute bootstrap.ps1)." }
}
$pgDump = Find-PgTool "pg_dump"
Write-Ok "PostgreSQL: $(& $pgDump --version)"

if (-not $SkipServices) {
    # Actualización: se detienen los servicios propios (y sus procesos) antes de reemplazar binarios.
    Stop-TopicoServices -Ports @($WebPort, $ApiPort)
}
foreach ($port in $WebPort, $ApiPort) {
    $listener = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($listener) {
        $owner = (Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)").CommandLine
        if ($owner -notmatch "TopicoCSJ|caddy|uvicorn app\.main") {
            throw "El puerto $port está en uso por otro programa: $owner"
        }
    }
}
Write-Ok "Puertos $WebPort y $ApiPort disponibles (o usados por esta misma aplicación)"

foreach ($tool in "caddy.exe", "WinSW-x64.exe") {
    $path = Join-Path $BinDir $tool
    if (-not (Test-Path $path)) { & (Join-Path $PSScriptRoot "get-tools.ps1") -BinDir $BinDir }
    if (-not (Test-ToolHash $path)) { throw "El binario $tool no supera la verificación SHA-256." }
}
Write-Ok "Caddy y WinSW verificados (SHA-256)"

foreach ($dir in $Dirs.Values) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
New-Item -ItemType Directory -Force -Path (Join-Path $Dirs.Logs "api"), (Join-Path $Dirs.Logs "web"), (Join-Path $Dirs.Logs "backup") | Out-Null

# ------------------------------------------------------------------------------- 2. Backend
Write-Step "Backend (Python)"
if (-not (Test-Path $VenvPython)) {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($launcher) { & py -3.12 -m venv (Join-Path $BackendDir ".venv") } else { & python -m venv (Join-Path $BackendDir ".venv") }
    if ($LASTEXITCODE -ne 0) { throw "No se pudo crear el entorno virtual (se requiere Python 3.12)." }
}
Push-Location $BackendDir
try {
    Invoke-Native { & $VenvPython -m pip install --quiet --disable-pip-version-check --upgrade pip } | Out-Null
    $out = Invoke-Native { & $VenvPython -m pip install --quiet --disable-pip-version-check -e . }
    if ($LASTEXITCODE -ne 0) { throw "Falló la instalación de dependencias del backend: $($out | Out-String)" }
    $basePrefix = "$(Invoke-Native { & $VenvPython -c "import sys; print(sys.base_prefix)" })".Trim()
    Write-Ok "Dependencias instaladas (Python base: $basePrefix)"

    # Configuración de producción (conserva lo que el administrador haya definido, p. ej. SMTP)
    $secret = $envValues["JWT_SECRET"]
    if (-not $secret -or $secret.Length -lt 32 -or $secret -match "CAMBIAR") { $secret = New-RandomSecret 64 }
    if (-not $HostNames -or $HostNames.Count -eq 0) {
        $fqdn = try { [Net.Dns]::GetHostEntry($env:COMPUTERNAME).HostName } catch { $env:COMPUTERNAME }
        $ips = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
            Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } | Select-Object -ExpandProperty IPAddress
        # Sin dominio (WORKGROUP) los equipos no resuelven el nombre del servidor: se prioriza la IP.
        $inDomain = (Get-CimInstance Win32_ComputerSystem).PartOfDomain
        $HostNames = $(if ($inDomain) { @($fqdn) + @($ips) } else { @($ips) + @($fqdn) }) | Where-Object { $_ } | Select-Object -Unique
    }
    $scheme = if ($TlsMode -eq "none") { "http" } else { "https" }
    # Se conserva una URL definida por el administrador; la generada automáticamente se recalcula
    # (p. ej., al pasar de HTTPS a HTTP).
    $currentUrl = $envValues["PUBLIC_APP_URL"]
    $autoGenerated = (-not $currentUrl) -or ($currentUrl -match "^https?://[^/]+:$WebPort/consulta$")
    $publicUrl = if ($autoGenerated) { "${scheme}://$($HostNames[0]):$WebPort/consulta" } else { $currentUrl }
    Set-EnvValues $EnvFile @{
        ENVIRONMENT = "production"
        JWT_SECRET = $secret
        TRUSTED_PROXY_COUNT = "1"
        COOKIE_SECURE = $(if ($TlsMode -eq "none") { "false" } else { "true" })
        DOCS_ENABLED = "false"
        CORS_ORIGINS = ""
        LOG_DIR = (Join-Path $Dirs.Logs "api")
        LOG_JSON_CONSOLE = "true"
        EMAIL_FILE_DIR = (Join-Path $Dirs.Logs "emails")
        PUBLIC_APP_URL = $publicUrl
    } -Remove @("DEV_CLOCK_START", "FRONTEND_DIST")
    Write-Ok "backend\.env configurado para producción (secreto JWT, cookies seguras, proxy de confianza)"
    if ((Read-EnvFile $EnvFile)["EMAIL_BACKEND"] -ne "smtp") {
        Write-Warn "EMAIL_BACKEND no es 'smtp': los correos solo se registrarán en el log. Configure SMTP_* en backend\.env."
    }

    $out = Invoke-Native { & $VenvPython -m alembic upgrade head }
    if ($LASTEXITCODE -ne 0) { throw "Falló la migración de la base de datos: $($out | Out-String)" }
    Write-Ok "Esquema de base de datos actualizado ($(Invoke-Native { & $VenvPython -m alembic current } | Select-Object -Last 1))"

    $users = (Invoke-Native { & $VenvPython -c "import app.modules.registry;from sqlalchemy import func,select;from app.core.config import get_settings;from app.core.db import build_engine,build_session_factory;from app.modules.users.models import AppUser;s=get_settings();f=build_session_factory(build_engine(s.database_url,s));print(f().scalar(select(func.count()).select_from(AppUser)))" } | Select-Object -Last 1)
    if ("$users".Trim() -eq "0") {
        Write-Warn "No existen usuarios. Cree el administrador inicial:"
        Write-Host "      cd `"$BackendDir`"; .\.venv\Scripts\python -m app.cli create-admin --username admin --full-name `"Nombre Apellido`""
    }
}
finally { Pop-Location }

# ------------------------------------------------------------------------------ 3. Frontend
Write-Step "Frontend"
$dist = Join-Path $FrontendDir "dist"
if (-not $SkipFrontendBuild) {
    Push-Location $FrontendDir
    try {
        $out = Invoke-Native { & npm ci --no-audit --no-fund --loglevel=error }
        if ($LASTEXITCODE -ne 0) { throw "Falló 'npm ci': $($out | Out-String)" }
        $out = Invoke-Native { & npm run build }
        if ($LASTEXITCODE -ne 0) { throw "Falló el build del frontend: $($out | Out-String)" }
    }
    finally { Pop-Location }
}
if (-not (Test-Path (Join-Path $dist "index.html"))) { throw "No existe frontend\dist (ejecute sin -SkipFrontendBuild)." }
& robocopy $dist $Dirs.Web /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "Falló la copia del frontend (robocopy $LASTEXITCODE)." }
Write-Ok "Frontend publicado en $($Dirs.Web)"

# --------------------------------------------------------------------------------- 4. Caddy
Write-Step "Proxy web y HTTPS (Caddy)"
$caddyExe = Join-Path $Dirs.Services "caddy.exe"
# En una actualización, el binario está en uso por el servicio: se detiene antes de reemplazarlo
# (el servicio se reinstala e inicia más adelante).
if ((Get-Service $ServiceWeb -ErrorAction SilentlyContinue).Status -eq "Running") {
    Stop-Service $ServiceWeb -Force
    (Get-Service $ServiceWeb).WaitForStatus("Stopped", [TimeSpan]::FromSeconds(30))
}
Copy-Item (Join-Path $BinDir "caddy.exe") $caddyExe -Force
$addresses = @($HostNames) + @("localhost") | Select-Object -Unique
# Si alguien escribe http:// en el puerto HTTPS, se le redirige a https:// (en lugar de un error 400).
$httpToHttps = "`n`tservers {`n`t`tlistener_wrappers {`n`t`t`thttp_redirect`n`t`t`ttls`n`t`t}`n`t}"
switch ($TlsMode) {
    "internal" {
        $siteAddress = ($addresses | ForEach-Object { "https://${_}:$WebPort" }) -join ", "
        $tlsDirective = "tls internal"
        # Solo el puerto $WebPort: sin redirector HTTP en :80 (en este servidor lo usa otra aplicación)
        $globalTls = "skip_install_trust`n`tauto_https disable_redirects$httpToHttps"
        $hsts = 'Strict-Transport-Security "max-age=31536000"'
    }
    "files" {
        if (-not (Test-Path $CertFile) -or -not (Test-Path $KeyFile)) { throw "Indique -CertFile y -KeyFile existentes." }
        $siteAddress = ($addresses | ForEach-Object { "https://${_}:$WebPort" }) -join ", "
        $tlsDirective = "tls `"$CertFile`" `"$KeyFile`""
        $globalTls = "auto_https disable_redirects$httpToHttps"
        $hsts = 'Strict-Transport-Security "max-age=31536000"'
    }
    "none" {
        Write-Warn "Sin HTTPS: el tráfico (incluidas credenciales) viaja sin cifrar dentro de la red institucional."
        Write-Warn "Migre a HTTPS (-TlsMode files o internal) cuando TI provea un certificado confiable para los equipos."
        $siteAddress = "http://:$WebPort"
        $tlsDirective = ""
        $globalTls = "auto_https off"
        $hsts = ""
    }
}
$caddyfile = Join-Path $Dirs.Caddy "Caddyfile"
$template = Get-Content (Join-Path $PSScriptRoot "config\Caddyfile.template") -Raw -Encoding UTF8
$content = $template.Replace("{{CADDY_DATA}}", (Join-Path $Dirs.Caddy "data")).Replace("{{LOG_DIR}}", (Join-Path $Dirs.Logs "web")).
    Replace("{{GLOBAL_TLS}}", $globalTls).Replace("{{SITE_ADDRESS}}", $siteAddress).Replace("{{TLS_DIRECTIVE}}", $tlsDirective).
    Replace("{{HSTS}}", $hsts).Replace("{{API_PORT}}", "$ApiPort").Replace("{{WEB_ROOT}}", $Dirs.Web)
[IO.File]::WriteAllText($caddyfile, $content, (New-Object Text.UTF8Encoding $false))
$validation = Invoke-Native { & $caddyExe validate --config $caddyfile --adapter caddyfile }
if ($LASTEXITCODE -ne 0) {
    $validation | Select-Object -Last 5 | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
    throw "La configuración de Caddy no es válida."
}
Write-Ok "Caddyfile generado y validado ($siteAddress)"

# ----------------------------------------------------------------------------- 5. Servicios
if (-not $SkipServices) {
    Write-Step "Servicios de Windows"
    if ($ServiceAccount -eq "auto") {
        $ServiceAccount = if ($basePrefix -like "C:\Users\*") { "LocalSystem" } else { "LocalService" }
        if ($ServiceAccount -eq "LocalSystem") {
            Write-Warn "Python está instalado en un perfil de usuario ($basePrefix): se usará LocalSystem."
            Write-Warn "Recomendado: instalar Python 3.12 'para todos los usuarios' y reinstalar para usar LocalService (mínimo privilegio)."
        }
    }
    $accountXml = if ($ServiceAccount -eq "LocalService") {
        "<serviceaccount><domain>NT AUTHORITY</domain><user>LocalService</user></serviceaccount>"
    } else { "" }
    if ($ServiceAccount -eq "LocalService") {
        & icacls $AppRoot /grant "*S-1-5-19:(OI)(CI)RX" /Q | Out-Null        # LOCAL SERVICE: lectura
        & icacls $DataRoot /grant "*S-1-5-19:(OI)(CI)M" /Q | Out-Null        # LOCAL SERVICE: modificación
        Write-Ok "Permisos mínimos otorgados a LOCAL SERVICE"
    }
    $pgService = (Get-Service "postgresql*" | Select-Object -First 1).Name

    $definitions = @(
        @{ Id = $ServiceApi; Template = "service-api.xml.template"; Log = Join-Path $Dirs.Logs "api" },
        @{ Id = $ServiceWeb; Template = "service-web.xml.template"; Log = Join-Path $Dirs.Logs "web" }
    )
    foreach ($svc in $definitions) {
        $wrapper = Join-Path $Dirs.Services "$($svc.Id).exe"
        if (Get-Service $svc.Id -ErrorAction SilentlyContinue) {
            Invoke-Native { & $wrapper stop } | Out-Null
            Invoke-Native { & $wrapper uninstall } | Out-Null
        }
        # Espera a que el proceso del servicio termine de verdad (libera el ejecutable y el puerto).
        for ($i = 0; $i -lt 60; $i++) {
            $running = Get-CimInstance Win32_Process -Filter "Name='$($svc.Id).exe'" -ErrorAction SilentlyContinue
            if (-not $running -and -not (Get-Service $svc.Id -ErrorAction SilentlyContinue)) { break }
            Start-Sleep -Seconds 1
        }
        if (-not ((Test-Path $wrapper) -and (Test-ToolHash (Join-Path $BinDir "WinSW-x64.exe")) -and
                  ((Get-FileHash $wrapper).Hash -eq (Get-FileHash (Join-Path $BinDir "WinSW-x64.exe")).Hash))) {
            Copy-Item (Join-Path $BinDir "WinSW-x64.exe") $wrapper -Force
        }
        $xml = (Get-Content (Join-Path $PSScriptRoot "config\$($svc.Template)") -Raw -Encoding UTF8).
            Replace("{{SERVICE_ID}}", $svc.Id).Replace("{{API_PORT}}", "$ApiPort").Replace("{{WEB_PORT}}", "$WebPort").
            Replace("{{PYTHON}}", $VenvPython).Replace("{{WORKERS}}", "$Workers").Replace("{{BACKEND_DIR}}", $BackendDir).
            Replace("{{PG_SERVICE}}", $pgService).Replace("{{LOG_DIR}}", $svc.Log).Replace("{{SERVICE_ACCOUNT}}", $accountXml).
            Replace("{{CADDY}}", $caddyExe).Replace("{{CADDYFILE}}", $caddyfile).Replace("{{CADDY_HOME}}", $Dirs.Caddy).
            Replace("{{API_SERVICE}}", $ServiceApi)
        [IO.File]::WriteAllText((Join-Path $Dirs.Services "$($svc.Id).xml"), $xml, (New-Object Text.UTF8Encoding $false))
        $out = Invoke-Native { & $wrapper install }
        if ($LASTEXITCODE -ne 0) { throw "No se pudo registrar el servicio $($svc.Id): $($out | Out-String)" }
        $out = Invoke-Native { & $wrapper start }
        if ($LASTEXITCODE -ne 0) { throw "No se pudo iniciar el servicio $($svc.Id): $($out | Out-String)" }
        Write-Ok "Servicio $($svc.Id) registrado e iniciado ($ServiceAccount)"
    }
}

# ------------------------------------------------------------------------------- 6. Firewall
if (-not $SkipFirewall) {
    Write-Step "Firewall de Windows"
    $ruleName = "TopicoCSJ Web ($WebPort)"
    Get-NetFirewallRule -DisplayName "TopicoCSJ Web*" -ErrorAction SilentlyContinue | Remove-NetFirewallRule
    New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Protocol TCP -LocalPort $WebPort -Action Allow `
        -Profile Domain, Private -Description "Tópico de Salud CSJ Lima (interfaz web HTTPS)" | Out-Null
    Write-Ok "Entrada permitida en TCP $WebPort (perfiles Dominio/Privado). La API ($ApiPort) no se expone."
}

# ------------------------------------------------------------------------ 7. Tareas programadas
if (-not $SkipTasks) {
    Write-Step "Tareas programadas"
    $ps = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
    $backupDir = Join-Path $PSScriptRoot "backup"
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2) -MultipleInstances IgnoreNew
    $tasks = @(
        @{ Name = "$TaskPrefix - Backup diario"; Script = "backup.ps1"; Trigger = New-ScheduledTaskTrigger -Daily -At $BackupTime },
        @{ Name = "$TaskPrefix - Verificacion de backup"; Script = "verify-backup.ps1"; Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At "03:00" },
        @{ Name = "$TaskPrefix - Verificacion de auditoria"; Script = "verify-audit.ps1"; Trigger = New-ScheduledTaskTrigger -Daily -At "06:30" }
    )
    foreach ($task in $tasks) {
        $taskArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$(Join-Path $backupDir $task.Script)`" -DataRoot `"$DataRoot`" -AppRoot `"$AppRoot`""
        $action = New-ScheduledTaskAction -Execute $ps -Argument $taskArgs
        Register-ScheduledTask -TaskName $task.Name -Action $action -Trigger $task.Trigger -Principal $principal -Settings $settings -Force | Out-Null
        Write-Ok $task.Name
    }
}

# --------------------------------------------------------------------------- 8. Verificación
if (-not $SkipServices) {
    Write-Step "Verificación final"
    $scheme = if ($TlsMode -eq "none") { "http" } else { "https" }
    $healthy = $false
    for ($i = 0; $i -lt 30 -and -not $healthy; $i++) {
        Start-Sleep -Seconds 2
        $out = Invoke-Native { & curl.exe -sk --noproxy "*" --max-time 5 "${scheme}://localhost:$WebPort/api/v1/health/ready" }
        $healthy = "$out" -match '"database":"ok"'
    }
    if ($healthy) { Write-Ok "Sistema operativo: $out" } else { Write-Warn "La verificación de salud no respondió a tiempo. Revise .\status.ps1 y $($Dirs.Logs)." }
}

Write-Host ""
Write-Host "Instalación completada." -ForegroundColor Green
$url = if ($TlsMode -eq "none") { "http://$($HostNames[0]):$WebPort" } else { "https://$($HostNames[0]):$WebPort" }
Write-Host "  Acceso:            $url"
Write-Host "  Consulta pública:  $url/consulta"
if ($TlsMode -eq "internal") {
    $root = Join-Path $Dirs.Caddy "data\pki\authorities\local\root.crt"
    Write-Host "  Certificado raíz a distribuir a los equipos cliente (GPO): $root" -ForegroundColor Yellow
}
Write-Host "  Diagnóstico:       .\status.ps1"
