# Guía de despliegue — Windows Server

Procedimiento para instalar, actualizar y operar el Sistema del Tópico de Salud en un servidor de la CSJ Lima. Es válido para Windows Server 2016/2019/2022 y no requiere Docker ni servicios en la nube.

## 1. Arquitectura de despliegue

```
 Equipos de la LAN (navegador)
          │  HTTPS  :42000   ← único puerto abierto en el firewall
          ▼
 ┌─────────────────────────────── Servidor ────────────────────────────────┐
 │  Servicio TopicoCSJ-Web  (Caddy)                                        │
 │    • sirve la interfaz (archivos estáticos)                             │
 │    • HTTPS, cabeceras de seguridad, CSP, compresión                     │
 │    • /api/*  ──►  127.0.0.1:42001                                       │
 │                                                                         │
 │  Servicio TopicoCSJ-API  (FastAPI/Uvicorn, 2 workers)  solo 127.0.0.1   │
 │    • reglas de negocio, auditoría, envío de correos (hilo interno)      │
 │          │                                                              │
 │          ▼                                                              │
 │  PostgreSQL 16 (servicio postgresql-x64-16)                             │
 │                                                                         │
 │  Tareas programadas: backup diario · verificación semanal · auditoría   │
 └─────────────────────────────────────────────────────────────────────────┘
```

| Componente | Puerto | Exposición |
|---|---|---|
| Web (Caddy) | **42000** (HTTPS) | Red institucional (perfiles Dominio y Privado) |
| API (FastAPI) | **42001** | Solo `127.0.0.1`; no es accesible desde otros equipos |
| PostgreSQL | 5432 | Según la configuración de `pg_hba.conf` |

> En este servidor, los puertos 80, 5173, 5180, 8000 y 8010 ya los usan otras aplicaciones. El instalador verifica que 42000 y 42001 estén libres, y Caddy no abre el puerto 80.

## 2. Requisitos

| Requisito | Versión | Notas |
|---|---|---|
| Windows Server | 2016 o superior | PowerShell 5.1 incluido |
| PostgreSQL | 16 | Servicio en el mismo servidor, o accesible desde él |
| Python | 3.12 | **Recomendado: instalación "para todos los usuarios"** (ver 6.3) |
| Node.js | 20 LTS | Solo para compilar el frontend |
| Espacio en disco | ≥ 10 GB libres | Backups y logs |
| Herramientas | Caddy 2.11.4 y WinSW 2.12.0 | Las descarga `get-tools.ps1`, verificando su SHA-256 |

**Servidor sin Internet:** descargue las dependencias en otro equipo y cópielas:
- **Python:** `pip download -d wheelhouse -e backend`; luego `pip install --no-index --find-links wheelhouse -e .`.
- **Node:** copie `node_modules`, o directamente `frontend\dist` ya compilado, e instale con `-SkipFrontendBuild`.
- **Binarios:** coloque `caddy.exe` y `WinSW-x64.exe` en `deploy\windows\bin\`. El instalador verifica su SHA-256 igualmente.

## 3. Instalación inicial

Todos los comandos se ejecutan en **PowerShell como Administrador**.

### 3.1 Obtener el código

```powershell
cd E:\PROGRAMACION
git clone https://github.com/edergc/TopicoCSJLima.git
cd TopicoCSJLima
```

### 3.2 Base de datos (una sola vez)

```powershell
powershell -ExecutionPolicy Bypass -File database\bootstrap\bootstrap.ps1
```

Crea:
- los roles `topico_owner`, `topico_app` y `topico_readonly`;
- las bases `topico_csj`, `topico_csj_verify` (para verificar backups) y `topico_csj_test`;
- el archivo `backend\.env` con contraseñas aleatorias.

Pide la contraseña del superusuario `postgres`, que no se guarda. Si se vuelve a ejecutar, rota las contraseñas.

### 3.3 Instalar

```powershell
powershell -ExecutionPolicy Bypass -File deploy\windows\install.ps1
```

El instalador:
1. Verifica los prerrequisitos, los puertos y la integridad de los binarios.
2. Instala las dependencias del backend y configura `backend\.env` para producción: secreto JWT, cookies seguras, proxy de confianza y documentación de la API deshabilitada.
3. Aplica las migraciones de la base de datos.
4. Compila el frontend y lo publica en la carpeta de datos.
5. Genera y valida la configuración de Caddy (HTTPS).
6. Registra los servicios `TopicoCSJ-API` y `TopicoCSJ-Web`, con inicio automático y reinicio ante fallos.
7. Abre el puerto 42000 en el firewall.
8. Programa las tareas de backup y de verificación.
9. Comprueba que el sistema responda.

**Parámetros útiles:**

| Parámetro | Por defecto | Uso |
|---|---|---|
| `-DataRoot` | `..\TopicoCSJ-data` | Carpeta de datos (web, logs, backups, certificados) |
| `-WebPort` / `-ApiPort` | 42000 / 42001 | Puertos |
| `-HostNames` | nombre del equipo + IPs | Nombres por los que acceden los usuarios (van en el certificado) |
| `-TlsMode` | `internal` | `internal` (CA propia), `files` (certificado institucional) o `none` (solo pruebas) |
| `-CertFile` / `-KeyFile` | — | Con `-TlsMode files` |
| `-Workers` | 2 | Procesos de la API |
| `-BackupTime` | 22:00 | Hora del backup diario |
| `-SkipFrontendBuild` | — | Usa el `frontend\dist` existente |

### 3.4 Crear el administrador inicial

```powershell
cd backend
.\.venv\Scripts\python -m app.cli create-admin --username admin --full-name "Nombre Apellido"
# o con contraseña temporal generada (cambio obligatorio en el primer ingreso):
.\.venv\Scripts\python -m app.cli create-admin --username admin --full-name "Nombre Apellido" --temporary
```

Pide la contraseña de forma interactiva, crea el usuario con acceso a todas las sedes y lo registra en la auditoría. Los demás usuarios se crean desde **Administración → Usuarios y roles**.

### 3.5 HTTP o HTTPS — decisión vigente

**Configuración actual: HTTP en la LAN** (`install.ps1 -TlsMode none`), acceso en `http://172.20.1.51:42000`.

**Motivo:** el servidor no pertenece a un dominio (WORKGROUP), no hay una CA institucional disponible ni un nombre DNS. Con HTTPS, cada PC mostraría "La conexión no es privada" hasta instalar el certificado a mano en todos los equipos de ambas sedes. Acostumbrar al personal a ignorar esa advertencia es peor para la seguridad.

**Riesgo aceptado:** dentro de la red institucional, el tráfico (credenciales, DNI, nombres, atenciones) viaja sin cifrar y podría ser capturado por alguien con acceso a la red.

**Controles que se mantienen:**
- solo el puerto 42000 abierto;
- API accesible solo desde el propio servidor;
- contraseñas con Argon2id y bloqueo por intentos;
- sesiones cortas;
- auditoría inalterable;
- CSP estricta.

**Migración a HTTPS** (un comando), cuando TI disponga de alguna de estas opciones:
- un certificado emitido por una CA que los equipos ya reconozcan, más un nombre DNS (`-TlsMode files`);
- la distribución del certificado raíz a los equipos mediante la consola de dominio de la PJ (`-TlsMode internal`).

Con HTTPS activo, `http://` se redirige automáticamente a `https://` en el mismo puerto.

### 3.6 Certificado HTTPS (cuando se adopte)

**Opción A — CA interna de Caddy (`-TlsMode internal`, por defecto).** Caddy emite su propio certificado. Para que los navegadores no muestren advertencias, distribuya el certificado raíz a los equipos de la red:

- Archivo: `TopicoCSJ-data\caddy\data\pki\authorities\local\root.crt`
- **Por GPO (recomendado):** *Configuración del equipo → Directivas → Configuración de Windows → Configuración de seguridad → Directivas de clave pública → Entidades de certificación raíz de confianza → Importar*.
- **Equipo individual:** `certutil -addstore -f Root root.crt` (como administrador).

**Opción B — Certificado institucional (`-TlsMode files`).** Si el área de TI emite certificados:

```powershell
.\install.ps1 -TlsMode files -HostNames topico.csjlima.gob.pe -CertFile C:\certs\topico.crt -KeyFile C:\certs\topico.key
```

Registre en el DNS interno el nombre (p. ej., `topico.csjlima.gob.pe`) apuntando a la IP del servidor.

### 3.7 Correo institucional (SMTP)

Edite `backend\.env`:

```ini
EMAIL_BACKEND=smtp
SMTP_HOST=smtp.institucion.gob.pe
SMTP_PORT=587
SMTP_SECURITY=starttls        # starttls | ssl | none
SMTP_USERNAME=topico@institucion.gob.pe
SMTP_PASSWORD=********
SMTP_FROM=Tópico de Salud CSJ Lima <topico@institucion.gob.pe>
```

Pruebe la configuración y reinicie la API:

```powershell
cd backend; .\.venv\Scripts\python -m app.cli send-test-email --to su.correo@pj.gob.pe
Restart-Service TopicoCSJ-API -Force; Start-Service TopicoCSJ-Web
```

### 3.8 Verificación posterior a la instalación

```powershell
deploy\windows\status.ps1
```

- [ ] Los servicios `TopicoCSJ-API`, `TopicoCSJ-Web` y PostgreSQL están en ejecución.
- [ ] La API escucha solo en `127.0.0.1:42001`.
- [ ] `http://<servidor>:42000` abre la pantalla de inicio de sesión desde **otro equipo** de la red.
- [ ] `http://<servidor>:42000/pantalla` muestra la pantalla de turnos.
- [ ] El administrador inicial puede ingresar.
- [ ] Llega el correo de prueba (si SMTP está configurado).
- [ ] Un backup manual funciona: `deploy\windows\backup\backup.ps1`.
- [ ] La verificación de restauración funciona: `deploy\windows\backup\verify-backup.ps1`.

### 3.9 TV de la sala de espera (pantalla de turnos)

Cualquier PC o mini-PC conectado a la TV, con Chrome o Edge, en la red institucional. Para que arranque sola, sin clics y con sonido, cree un acceso directo en la carpeta *Inicio* (`shell:startup`) del usuario de ese equipo:

```
"C:\Program Files\Google\Chrome\Application\chrome.exe" --kiosk --autoplay-policy=no-user-gesture-required --no-first-run http://172.20.1.51:42000/pantalla/alz
```

(`/pantalla/bar` para la sede Anselmo Barreto). Con `--kiosk` se muestra a pantalla completa; `Alt+F4` la cierra. Configure el equipo para que **no suspenda ni apague la pantalla** (Opciones de energía → Nunca). En HTTP el navegador no permite bloquear el reposo desde la página.

## 4. Actualización a una nueva versión

```powershell
cd E:\PROGRAMACION\TopicoCSJLima
deploy\windows\backup\backup.ps1            # backup previo (recomendado)
git pull
powershell -ExecutionPolicy Bypass -File deploy\windows\install.ps1
```

El instalador es idempotente: actualiza las dependencias, aplica las migraciones nuevas, recompila el frontend y reinicia los servicios. Conserva `backend\.env` (incluida la configuración SMTP) y los certificados.

## 5. Operación diaria

| Tarea | Comando |
|---|---|
| Estado general | `deploy\windows\status.ps1` |
| Reiniciar la API (reinicia también la web, que depende de ella) | `Restart-Service TopicoCSJ-API -Force; Start-Service TopicoCSJ-Web` |
| Reiniciar la web | `Restart-Service TopicoCSJ-Web` |
| Detener todo | `Stop-Service TopicoCSJ-Web, TopicoCSJ-API` |
| Verificar la auditoría | `deploy\windows\backup\verify-audit.ps1` |

**Dónde están los logs** (dentro de `TopicoCSJ-data\logs\`):

| Carpeta | Contenido |
|---|---|
| `api\app.log*` | Logs técnicos JSON (errores, solicitudes, correos), rotación diaria, 90 días |
| `api\TopicoCSJ-API.*.log` | Salida del servicio (arranque, errores fatales) |
| `web\access.log` | Accesos HTTP (Caddy) |
| `web\caddy.log` | Eventos del proxy y los certificados |
| `backup\backup-AAAA-MM.log` | Backups, verificaciones y restauraciones |
| `backup\audit-AAAA-MM.log` | Verificación diaria de la auditoría |

Cada respuesta de la API incluye la cabecera `X-Request-ID`, que aparece también en los logs y en la auditoría. Si un usuario reporta un error, el código de solicitud que ve en pantalla permite ubicarlo.

## 6. Seguridad del despliegue

1. **Superficie mínima:** solo el puerto 42000 queda expuesto. La API y PostgreSQL no son accesibles desde la red, salvo que `pg_hba.conf` lo permita; conviene revisarlo.
2. **Protección de la IP del cliente:** Caddy reemplaza `X-Forwarded-For`, así que un cliente no puede falsear su IP en la auditoría (verificado en las pruebas de despliegue).
3. **Cuenta de servicio:** si Python está instalado para todos los usuarios, los servicios corren como `LOCAL SERVICE`, con lectura del código y escritura solo en `TopicoCSJ-data`. Si Python está en el perfil de un usuario, se usa `LocalSystem` y el instalador lo advierte. **Recomendación:** reinstalar Python 3.12 "para todos los usuarios" y ejecutar de nuevo el instalador.
4. **Secretos:**
   - `backend\.env` contiene las contraseñas de la base de datos y el secreto JWT.
   - Restrinja su acceso: `icacls backend\.env /inheritance:r /grant Administradores:F /grant "NT AUTHORITY\SYSTEM:F" /grant "NT AUTHORITY\LOCAL SERVICE:R"`.
   - Nunca lo versione (está en `.gitignore`).
5. **Rotación de contraseñas de la base de datos:** vuelva a ejecutar `bootstrap.ps1` y luego `Restart-Service TopicoCSJ-API -Force; Start-Service TopicoCSJ-Web`.
6. **PostgreSQL:** mantenga actualizado el servidor y limite en `pg_hba.conf` las redes que pueden conectarse.

## 7. Desinstalación

```powershell
powershell -ExecutionPolicy Bypass -File deploy\windows\uninstall.ps1
```

Retira los servicios, la regla de firewall y las tareas programadas. **No** borra la base de datos, los backups, los logs ni el código. Para volver a instalar, basta ejecutar `install.ps1`.

## 8. Solución de problemas

| Síntoma | Causa probable | Acción |
|---|---|---|
| El instalador dice "El puerto 42000 está en uso" | Otra aplicación lo ocupa | `Get-NetTCPConnection -LocalPort 42000`; use `-WebPort` con otro puerto |
| `TopicoCSJ-Web` se detiene al iniciar | Error de configuración o de puerto | Revise `logs\web\TopicoCSJ-Web.*.log` y `caddy.log` |
| El navegador advierte "sitio no seguro" | Falta el certificado raíz de la CA interna | Distribuya `root.crt` (sección 3.5) |
| La pantalla carga, pero dice "No se pudo conectar con el servidor" | API detenida | `Get-Service TopicoCSJ-API`; revise `logs\api\` |
| `/api/v1/health/ready` responde 503 | PostgreSQL no disponible | `Get-Service postgresql*`; revise las credenciales en `.env` |
| No llegan correos | SMTP mal configurado o `EMAIL_BACKEND` distinto de `smtp` | `app.cli send-test-email`; revise `logs\api\app.log` (`notification_failed`) |
| "Su sesión ha finalizado" continuamente | El reloj del servidor está desincronizado | Sincronice la hora (`w32tm /resync`) |
| Usuario bloqueado | Varios intentos fallidos | Administración → Usuarios → Desbloquear |
| `status.ps1` marca el backup en falla | La tarea no se ejecutó o falló | `logs\backup\`; ejecute `backup.ps1` manualmente |

## 9. Alternativa Linux (referencia)

La aplicación es multiplataforma. En Linux:
- **API:** un servicio `systemd` con `uvicorn app.main:create_app --factory --host 127.0.0.1 --port 42001 --workers 2`.
- **Web:** Caddy (paquete oficial), con el mismo Caddyfile cambiando las rutas.
- **Backups:** `pg_dump` desde `cron`, con la misma política de retención.

Los scripts `.ps1` de este repositorio sirven como especificación de los pasos.
