# Manual técnico

Dirigido al equipo de TI que mantendrá y ampliará el sistema. Complementa:
- `01-analisis-y-diseno.md`: requerimientos, decisiones y reglas de negocio;
- `02-modelo-datos.md`: modelo de datos;
- `04-api.md`: API;
- `05-despliegue.md`: instalación;
- `06-backup-restauracion.md`: backups.

## 1. Vista general

| Capa | Tecnología | Ubicación |
|---|---|---|
| Interfaz | React 19, TypeScript estricto, Vite 8, Tailwind 4, Radix UI, TanStack Query | `frontend/` |
| API | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 (síncrono), psycopg 3 | `backend/app/` |
| Base de datos | PostgreSQL 16, esquema `topico`, migraciones Alembic con DDL en SQL | `backend/alembic/` |
| Proxy / HTTPS | Caddy 2 | `deploy/windows/config/` |
| Servicios | WinSW (Windows) | `deploy/windows/` |

**Estilo:** monolito modular. Un proceso, una base de datos, módulos de dominio con límites claros. Sin colas externas ni microservicios (decisión explicada en `01`, sección 6).

## 2. Backend

### 2.1 Capas y responsabilidades

```
router (HTTP) → servicio (regla de negocio + transacción) → ORM/SQL → PostgreSQL (restricciones finales)
```

- **Router** (`modules/*/router.py`): valida la entrada con Pydantic, obtiene el `ServiceContext` y llama al servicio. No contiene reglas.
- **Servicio** (`modules/*/service.py`): implementa el caso de uso completo y **delimita la transacción** (`commit`), incluyendo el evento de la atención, la auditoría y la notificación.
- **Base de datos:** última línea de defensa. Garantiza la capacidad, la numeración, las transiciones válidas, la unicidad y la inmutabilidad (ver `02`).

### 2.2 Módulos

| Módulo | Contenido principal |
|---|---|
| `core/` | Configuración (`config.py`), BD (`db.py`), errores uniformes (`errors.py`), seguridad (Argon2id, JWT), logging JSON, middlewares (request_id, IP real, cabeceras), reloj (`clock.py`), rate limit, entrega opcional del frontend |
| `auth/` | Login, refresh rotativo con detección de reutilización, cambio de contraseña, `require(permiso)`, `ServiceContext`, proveedores de autenticación |
| `users/` | Usuarios, roles, permisos, alcance por sede |
| `sites/` | Sedes, configuración versionada, horarios, cierres, disponibilidad, ventana de registro |
| `workers/` | Trabajadores, dependencias, cobertura EPS, elegibilidad |
| `appointments/` | Máquina de estados, registro, transiciones, llamar siguiente, vista de cola, hora estimada |
| `notifications/` | Outbox, plantillas Jinja2 en sandbox, canal SMTP, hilo de despacho con reintentos |
| `imports/` | Lectura de Excel con sinónimos de columnas, staging, confirmación transaccional |
| `reports/` | Agregados y exportación (CSV/XLSX) |
| `audit/` | Registro (en la transacción o aislado) y verificación de la cadena |
| `admin/` | Parámetros, motivos, plantillas |
| `public/` | Consulta pública del turno |

### 2.3 Flujo: registrar una atención

```mermaid
sequenceDiagram
    participant UI as Mesa de atención
    participant API as AppointmentService
    participant DB as PostgreSQL
    participant W as Hilo de notificaciones
    UI->>API: POST /appointments {site_id, dni, canal}
    API->>API: permiso + sede autorizada
    API->>DB: elegibilidad (trabajador activo + EPS vigente)
    API->>DB: horario, cierres, ventana de registro, re-registro
    API->>DB: ensure_service_day() + SELECT … FOR NO KEY UPDATE (serializa la sede/día)
    API->>DB: INSERT appointment (el trigger asigna turno y ocupa cupo; CHECK impide exceso)
    API->>DB: INSERT appointment_event + audit_event + notification(PENDING)
    API->>DB: COMMIT (todo o nada)
    API-->>UI: 201 {turno, posición, hora estimada}
    W->>DB: toma PENDING (SKIP LOCKED) y envía por SMTP con reintentos
```

### 2.4 Decisiones técnicas relevantes

| Tema | Decisión | Motivo |
|---|---|---|
| Concurrencia de cupos | Bloqueo de la fila `service_day`, más un contador mantenido por trigger con `CHECK` | Dos encargadas no pueden exceder la capacidad (probado con 12 conexiones simultáneas) |
| Bloqueos | `FOR NO KEY UPDATE` en lugar de `FOR UPDATE` | Evita deadlocks con las inserciones que referencian la fila por clave foránea (auditoría, eventos) |
| Llamar siguiente | `FOR UPDATE SKIP LOCKED` | Dos usuarios nunca llaman a la misma persona |
| Edición concurrente | Columna `version` (optimistic locking) | Detecta que otro usuario cambió la atención (`409 APPOINTMENT_CHANGED`) |
| Hora | UTC en la BD y `America/Lima` para la fecha operativa; `Clock` inyectable; el frontend sincroniza con la hora del servidor | Evita errores de zona horaria y el desfase del reloj de los PC |
| Notificaciones | Patrón outbox en la misma transacción | No sale un correo de una operación revertida; sin Redis/Celery |
| Auditoría | Solo inserción, con cadena SHA-256 calculada en la BD | Detecta alteraciones incluso por usuarios con privilegios |
| Errores | `{success, code, message, details, request_id}` | Código estable para el frontend; mensaje en español; sin trazas |

### 2.5 Configuración

- **Técnica:** `backend/.env` (ver `.env.example`, comentado variable por variable).
- **De negocio:** en la base de datos, editable desde la aplicación: capacidad, horario, tolerancia, motivos, plantillas y parámetros. **Nunca** se codifica en el programa.

### 2.6 Comandos (`python -m app.cli`)

| Comando | Uso |
|---|---|
| `create-admin --username U --full-name "N"` | Primer administrador |
| `verify-audit` | Verifica la cadena de auditoría (código 2 si hay alteraciones) |
| `send-test-email --to correo` | Prueba la configuración de correo |

Scripts de soporte (`backend/scripts/`):
- `generate_data_dictionary.py`: regenera `docs/03`;
- `seed_demo.py`: datos de capacitación, bloqueado en producción.

## 3. Frontend

- **Organización por funcionalidad** (`src/features/*`). La capa compartida (`src/shared/*`) contiene el cliente HTTP, la autenticación, el sistema de diseño, los gráficos y las utilidades.
- **Sin reglas de negocio en React:** las acciones posibles llegan en `allowed_actions`. La interfaz solo decide cómo mostrarlas.
- **Tipos generados** desde el OpenAPI: `npm run gen:api` tras cualquier cambio en la API.
- **Estado del servidor** con TanStack Query. La cola se consulta cada 5 s mientras la pestaña está visible.
- **Sesión:** el access token vive solo en memoria y el refresh en una cookie HttpOnly con `SameSite=Strict`. Si varias solicitudes reciben 401 a la vez, la sesión se renueva una sola vez.
- **Sistema de diseño:**
  - tokens en `src/styles/index.css`;
  - componentes en `src/shared/ui`;
  - semántica de estados en `src/shared/lib/status.ts`.

  Para ajustarlo al manual de identidad del Poder Judicial basta modificar los tokens `--color-brand-*` y `BrandMark.tsx`.

## 4. Seguridad (resumen)

| Control | Implementación |
|---|---|
| Contraseñas | Argon2id (parámetros OWASP) y política de longitud y composición; cambio obligatorio de la clave temporal |
| Fuerza bruta | Bloqueo temporal por intentos fallidos (parámetro) y rate limit en login, refresh y consulta pública |
| Sesiones | JWT de 15 min; refresh rotativo, revocable y con detección de robo; cierre de sesiones al cambiar la clave o desactivar al usuario |
| Autorización | Permisos atómicos y alcance por sede, validados en el backend; accesos denegados auditados |
| CSRF | API con Bearer; el refresh exige `SameSite=Strict` y la cabecera `X-Requested-With` |
| XSS | React con escape por defecto, `dangerouslySetInnerHTML` prohibido por lint, CSP `script-src 'self'` y plantillas de correo en sandbox |
| Inyección SQL | Solo consultas parametrizadas (ORM/psycopg) |
| Mínimo privilegio en la BD | La aplicación no tiene DDL ni `DELETE` en tablas de negocio, y actualiza por columna los datos sensibles |
| Privacidad | Sin datos clínicos; lecturas de ficha y exportaciones nominales auditadas; consulta pública con DNI y código y nombre enmascarado; pantalla de sala solo con código de turno y nombre abreviado (desactivable) |

## 5. Observabilidad

- **Logs técnicos JSON:** `logs/api/app.log`. Campos: `timestamp`, `level`, `logger`, `event`, `request_id`; `http_request` incluye método, ruta, estado, `elapsed_ms` e IP.
- **Eventos útiles para alertas:**
  - `unhandled_exception`: error 500;
  - `slow_query`: consulta mayor a `DB_SLOW_QUERY_MS`;
  - `notification_failed`: correo que agotó sus reintentos;
  - `integrity_error`;
  - `background_worker_error`.
- **Salud:** `/api/v1/health` (proceso) y `/api/v1/health/ready` (BD y versión del esquema).
- **Operación:** incidencias visibles en la mesa (tolerancia vencida, correos fallidos, capacidad baja) y `status.ps1` en el servidor.

## 6. Cómo extender (fases futuras)

| Fase | Punto de extensión |
|---|---|
| 2 · El trabajador solicita directamente | El canal `WEB` ya existe en el modelo. Crear un endpoint autenticado para trabajadores, reutilizando `AppointmentService.register` (mismas reglas). El estado `REGISTRADO` y `booking.advance_days_max` soportan fechas futuras. |
| 3 · AD/LDAP | Implementar `LdapAuthProvider` (protocolo en `auth/providers.py`) y registrarlo en `_PROVIDERS`. El campo `app_user.auth_provider` ya admite `LDAP`. |
| 4 · Integraciones | Nuevo módulo en `app/modules/`, con su servicio y la auditoría. La API REST está versionada (`/api/v1`). |
| 5 · Más canales de notificación | Implementar `Channel.send` (`notifications/channels.py`) y agregar el canal a la tabla de plantillas (`CHECK channel`), mediante una migración. |
| 6 · Paneles avanzados | Ampliar `reports/service.py` (agregados SQL) y usar los componentes de `shared/charts` con la paleta validada. |
| Prioridad especial | Regla explícita y auditada. Por ejemplo, una columna `priority` en la atención y el orden `(priority DESC, ticket_number)` en "llamar siguiente", con un permiso propio. |

## 7. Convenciones de desarrollo

1. **Cambios de base de datos:** siempre con una nueva migración (`alembic/sql/000N_*.sql` y `versions/000N_*.py`), con privilegios explícitos y `COMMENT ON`. Ver `database/README.md`.
2. **Pruebas obligatorias:** toda regla de negocio lleva pruebas (en `tests/api` o `tests/db`). Los 7 casos críticos no deben romperse.
3. **Calidad (debe quedar en verde antes de integrar):**
   - Backend: `ruff check . ; mypy app ; pytest`
   - Frontend: `npm run typecheck ; npm run lint ; npm test`
4. **Mensajes al usuario:** en español, en `core/errors.py` (backend). Los códigos de error son estables: si se renombra uno, hay que actualizar el frontend.
5. **Commits** descriptivos en español, por funcionalidad.

## 8. Entorno de desarrollo

```powershell
# Backend (puerto 42001)
cd backend; .\.venv\Scripts\uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port 42001
# Frontend (puerto 42000; /api se redirige a 42001)
cd frontend; npm run dev
```

> En el servidor de producción los puertos 42000 y 42001 los usan los servicios. Para desarrollar allí, detenga los servicios o use otros puertos (`VITE_API_TARGET`, `--port`).

Para desarrollo, `backend\.env` debe tener `ENVIRONMENT=development`. El instalador lo configura en `production`. En la base de pruebas se puede usar el reloj desplazado (`DEV_CLOCK_START`) con los datos de `seed_demo.py`, por ejemplo para capacitaciones.
