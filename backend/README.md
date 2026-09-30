# Backend — Tópico de Salud CSJ Lima

API REST en **Python 3.12 + FastAPI + SQLAlchemy 2 + PostgreSQL 16**. Es un monolito modular: un proceso y una base de datos, con módulos de dominio separados.

## Estructura

```
backend/
  app/
    main.py              Fábrica de la app (create_app): middlewares, routers, health
    cli.py               Comandos: create-admin, verify-audit, send-test-email
    core/                Configuración, BD, errores, seguridad, logs, reloj, rate limit
    shared/              Schemas base, paginación, normalización de textos/DNI
    modules/
      auth/              Login, sesiones rotativas, dependencias de permisos (require)
      users/             Usuarios, roles, permisos, alcance por sede
      sites/             Sedes, configuración versionada, horarios, cierres, disponibilidad
      workers/           Trabajadores, cobertura EPS, elegibilidad
      appointments/      Atenciones, máquina de estados, cola, hora estimada
      notifications/     Outbox, plantillas (Jinja2 sandbox), canal SMTP, worker de fondo
      imports/           Importación de Excel con staging y confirmación
      reports/           Indicadores agregados y exportación
      audit/             Auditoría funcional (registro y verificación de la cadena)
      admin/             Parámetros, motivos, plantillas
      public/            Consulta pública del turno
  alembic/               Migraciones (DDL en alembic/sql/*.sql)
  tests/
    db/                  Integridad de la BD (constraints, triggers, concurrencia)
    api/                 Casos de uso de punta a punta vía HTTP
    unit/                Dominio puro (máquina de estados, estimaciones)
```

**Capas:** el router traduce HTTP ↔ servicio; el servicio contiene la regla de negocio y delimita la transacción; la BD es la última línea de defensa (capacidad, turnos, transiciones, auditoría).

## Puesta en marcha (desarrollo)

```powershell
# 0) Una sola vez: roles y bases de datos (ver database/README.md)
powershell -ExecutionPolicy Bypass -File ..\database\bootstrap\bootstrap.ps1

# 1) Entorno e instalación
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -e ".[dev]"

# 2) Esquema de BD
.\.venv\Scripts\alembic upgrade head

# 3) Primer administrador (pide la contraseña de forma interactiva)
.\.venv\Scripts\python -m app.cli create-admin --username admin --full-name "Administrador del Sistema"

# 4) Ejecutar
.\.venv\Scripts\uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port 42001
```

- API: `http://localhost:42001/api/v1`
- Documentación interactiva (solo fuera de producción): `http://localhost:42001/api/v1/docs`
- En Windows, si la consola muestra caracteres extraños: `$env:PYTHONUTF8=1`

## Configuración

Toda la configuración técnica va en `backend/.env` (ver `.env.example`). Los parámetros de negocio (capacidad, horarios, tolerancia, etc.) **no** están en `.env`: se administran desde la aplicación y se guardan en la BD.

| Variable | Descripción |
|---|---|
| `DATABASE_URL` / `DATABASE_MIGRATION_URL` | Conexión de la app (rol mínimo) y de migraciones (propietario) |
| `JWT_SECRET` | Obligatorio en producción (≥ 32 caracteres) |
| `EMAIL_BACKEND` | `smtp`, `console` (desarrollo), `file`, `disabled` |
| `SMTP_*` | Servidor de correo institucional |
| `TRUSTED_PROXY_COUNT` | 1 si hay un proxy inverso (IIS/Caddy/Nginx) delante |
| `CORS_ORIGINS` | Solo en desarrollo (en producción el frontend y la API comparten origen) |

## Pruebas

```powershell
.\.venv\Scripts\python -m pytest            # todas (usa la BD topico_csj_test; la recrea)
.\.venv\Scripts\python -m pytest tests/db   # solo integridad de la BD
.\.venv\Scripts\ruff check . ; .\.venv\Scripts\mypy app
```

Los siete casos críticos del requerimiento tienen pruebas con nombre explícito (`test_caso_1_…` a `test_caso_7_…`), tanto a nivel de BD como de API. Las pruebas de concurrencia usan conexiones reales simultáneas.

## Comandos administrativos

```powershell
.\.venv\Scripts\python -m app.cli create-admin --username admin --full-name "Nombre"
.\.venv\Scripts\python -m app.cli verify-audit          # integridad de la auditoría (código 2 si hay alteraciones)
.\.venv\Scripts\python -m app.cli send-test-email --to usuario@pj.gob.pe
```

## Procesos en segundo plano

Dentro del mismo proceso (sin Redis ni Celery) corre un hilo que:
1. envía las notificaciones pendientes (outbox) con reintentos y backoff exponencial;
2. activa las atenciones `REGISTRADO` cuya fecha llegó (`→ EN_ESPERA`).

Es seguro con varios workers de Uvicorn porque las filas se reclaman con `FOR UPDATE SKIP LOCKED`.

Más detalle: `docs/04-api.md` (API y códigos de error) y `docs/02-modelo-datos.md` (modelo de datos).
