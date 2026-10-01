# API REST — Tópico de Salud CSJ Lima

- Base: `/api/v1`. La especificación OpenAPI completa está en `/api/v1/openapi.json` y la interfaz interactiva en `/api/v1/docs` (deshabilitadas en producción).
- Autenticación: `Authorization: Bearer <access_token>`. El access token dura 15 minutos y se renueva con `POST /auth/refresh` (cookie HttpOnly + cabecera `X-Requested-With: XMLHttpRequest`).
- Fechas: ISO-8601. Los instantes llevan zona horaria (UTC) y la fecha operativa (`service_date`) corresponde a America/Lima.
- Identificadores: UUID (`public_id`) para usuarios, trabajadores, atenciones y lotes. Las sedes usan un entero.
- Paginación: `?page=1&size=25`, con respuesta `{items, total, page, size}`.
- Cada respuesta incluye la cabecera `X-Request-ID`, que permite cruzarla con los logs técnicos y la auditoría.

## Formato de error

```json
{
  "success": false,
  "code": "CAPACITY_REACHED",
  "message": "Se ha alcanzado la capacidad máxima de atención para esta sede en la fecha seleccionada.",
  "details": null,
  "request_id": "9160b5f1d5e547e58272d92e007ab5b0"
}
```

`code` es estable (el frontend decide qué hacer según el código) y `message` está en español, listo para mostrar. En los errores de validación, `details` trae la lista `[{field, message}]`.

| HTTP | Uso |
|---|---|
| 400 | Solicitud mal formada |
| 401 | Sin sesión o sesión inválida/expirada (`UNAUTHORIZED`, `TOKEN_EXPIRED`, `SESSION_EXPIRED`, `INVALID_CREDENTIALS`, `ACCOUNT_LOCKED`) |
| 403 | Sin permiso (`FORBIDDEN`), sede no autorizada (`SITE_FORBIDDEN`), cambio de contraseña pendiente (`PASSWORD_CHANGE_REQUIRED`) |
| 404 | Recurso inexistente |
| 409 | Conflicto con el estado actual (`CAPACITY_REACHED`, `WORKER_ALREADY_HAS_APPOINTMENT`, `INVALID_TRANSITION`, `APPOINTMENT_CHANGED`, `MAX_IN_SERVICE_REACHED`) |
| 422 | Validación o regla de negocio (`VALIDATION_ERROR`, `WORKER_NOT_ELIGIBLE`, `TOLERANCE_NOT_ELAPSED`, `REASON_REQUIRED`, …) |
| 429 | Rate limit (`RATE_LIMITED`) |
| 500/503 | Error interno o BD no disponible (sin detalles internos) |

El catálogo completo de códigos y mensajes está en `backend/app/core/errors.py`.

## Endpoints

### Salud
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health` | Liveness |
| GET | `/health/ready` | Readiness: verifica PostgreSQL y la revisión del esquema |

### Autenticación
| Método | Ruta | Descripción |
|---|---|---|
| POST | `/auth/login` | `{username, password}` → access token + cookie de refresh (rate limit: 10/min) |
| POST | `/auth/refresh` | Rota la sesión (requiere `X-Requested-With`) |
| POST | `/auth/logout` | Revoca la sesión |
| GET | `/auth/me` | Perfil, roles, permisos y sedes |
| POST | `/auth/change-password` | Cambio de contraseña propia (cierra las demás sesiones) |

### Operación (mesa de la encargada)
| Método | Ruta | Permiso | Descripción |
|---|---|---|---|
| GET | `/workers/eligibility?document_number=` | `worker:lookup` | Búsqueda rápida por DNI: habilitación EPS y turno activo |
| GET | `/sites/{id}/availability?date=` | `site:read` | Capacidad, ocupados, disponibles y motivo de bloqueo |
| GET | `/sites/{id}/queue?date=` | `queue:read` | **Panel operativo**: indicadores, en atención, llamados, en espera (con posición y hora estimada), finalizados e incidencias |
| POST | `/sites/{id}/queue/call-next` | `appointment:operate` | LLAMAR SIGUIENTE |
| POST | `/appointments` | `appointment:create` | Registrar: `{site_id, document_number, channel: PHONE\|WALK_IN, admin_note?}` |
| GET | `/appointments?site_id&date_from&date_to&status&document_number` | `appointment:read` | Búsqueda |
| GET | `/appointments/{id}` · `/events` · `/notifications` | `appointment:read` | Detalle, línea de tiempo, correos |
| POST | `/appointments/{id}/call` · `/start` · `/finish` · `/requeue` | `appointment:operate` | Transiciones |
| POST | `/appointments/{id}/cancel` | `appointment:cancel` | `{reason_id, note?}` libera el cupo |
| POST | `/appointments/{id}/no-show` | `appointment:no_show` | Solo tras vencer la tolerancia; libera el cupo |
| POST | `/appointments/{id}/void` | `appointment:void` | Anular por error de registro; libera el cupo |

Todas las transiciones aceptan `{version}` para el control de concurrencia optimista. Cada atención devuelve `allowed_actions` según su estado y los permisos del usuario, de modo que el frontend no duplica la máquina de estados.

### Configuración de sede
| Método | Ruta | Permiso |
|---|---|---|
| GET / PATCH | `/sites/{id}` | `site:read` / `site:configure` |
| GET / POST | `/sites/{id}/settings` | configuración versionada (aplica desde mañana) |
| GET / PUT | `/sites/{id}/schedules` | horario semanal por bloques |
| GET / POST / DELETE | `/sites/{id}/closures` | días sin atención |
| GET / POST / PATCH | `/sites/{id}/doctors[/{doctor_id}]` | médicos de la sede (lectura: `site:read`; alta y cambios: `site:configure`). Al iniciar una atención, `POST /appointments/{id}/start` acepta `doctor_id` (obligatorio si hay más de un médico activo; con uno solo se asigna automáticamente) |
| PATCH | `/sites/{id}/service-days/{date}/capacity` | `service_day:adjust` (ajuste auditado del día) |

### Trabajadores e importación
| Método | Ruta | Permiso |
|---|---|---|
| GET | `/workers?q=` | `worker:read` |
| GET | `/workers/{id}` | `worker:read` (lectura auditada) |
| POST / PATCH | `/workers`, `/workers/{id}` | `worker:manage` |
| POST | `/workers/{id}/coverages`, `/coverages/{cid}/end` | `worker:manage` |
| POST | `/imports` (multipart `file`) | `import:manage`: carga y **valida** sin aplicar |
| GET | `/imports`, `/imports/{id}`, `/imports/{id}/rows?outcome=`, `/imports/{id}/errors.csv` | previsualización |
| POST | `/imports/{id}/confirm` `{deactivate_missing}` · `/imports/{id}/discard` | confirmación transaccional |

### Reportes, auditoría y notificaciones
| Método | Ruta | Permiso |
|---|---|---|
| GET | `/reports/summary?date_from&date_to&site_id` | `report:read` (agregados, sin datos personales) |
| GET | `/reports/export?report=summary\|daily\|appointments&format=pdf\|xlsx\|csv` | `summary` (PDF institucional o Excel con varias hojas) y `daily`: `report:read`. `appointments` (listado nominal): `report:export` + `report:read_nominal` |
| GET | `/audit-events?...` | `audit:read` |
| POST | `/audit-events/verify` | `audit:verify` |
| GET | `/notifications?status=` · POST `/notifications/{id}/resend` | `notification:read` / `notification:resend` |

### Administración
| Ruta | Permiso |
|---|---|
| `/admin/users` (GET, POST), `/admin/users/{id}` (GET, PATCH), `/reset-password`, `/unlock` | `user:read` / `user:manage` |
| `/admin/roles`, `/admin/roles/{id}/permissions`, `/admin/permissions` | `role:read` / `role:manage` |
| `/admin/parameters`, `/admin/parameters/{key}` | `parameter:manage` |
| `/admin/reasons` | `catalog:manage` |
| `/admin/notification-templates`, `/{id}/preview` | `template:manage` |
| `/catalogs/reasons`, `/catalogs/departments`, `/catalogs/appointment-statuses` | autenticado |

### Consulta pública (sin sesión)
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/public/ticket-status?document_number=&ticket_code=` | Requiere ambos datos. Devuelve estado, posición, personas delante y hora estimada. El nombre va enmascarado y no se exponen datos de terceros. Rate limit: 20/min |
| GET | `/public/display/sites` | Sedes activas con pantalla de turnos. Rate limit: 60/min |
| GET | `/public/display/{site_code}` | Pantalla de la sala de espera: turnos llamados (el más reciente primero, con `call_count` para detectar re-llamados), en atención y siguientes (máx. 8) con hora estimada. Solo código de turno y nombre abreviado ("Ana R."; `null` si `display.show_names` = false). 404 `DISPLAY_DISABLED` si `display.enabled` = false. Rate limit: 120/min |
