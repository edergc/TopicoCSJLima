# Sistema Integral de Gestión de Atención del Tópico de Salud — CSJ Lima

Sistema institucional de la **Corte Superior de Justicia de Lima** para gestionar la solicitud, la cola, el seguimiento y la trazabilidad de las atenciones de los tópicos de salud de las sedes **Javier Alzamora Valdez** y **Anselmo Barreto**, destinados a trabajadores con EPS Rímac.

Reemplaza el registro en Excel por una operación digital, con reglas de negocio aplicadas por el sistema, control de capacidad concurrente, notificaciones por correo, reportes y auditoría inalterable. **Es un sistema administrativo: no almacena información clínica.**

![Mesa de atención](docs/manual/img/02-mesa.png)

## Funcionalidades

- **Mesa de atención:** búsqueda por DNI con verificación EPS, turno generado al instante, cola en vivo con hora estimada, llamar siguiente (F4), inicio y fin de atención, y cancelación, no presentado o anulación con motivo.
- **Reglas del servicio:**
  - capacidad diaria configurable por sede;
  - horarios, cierres y tolerancia;
  - un turno activo por trabajador y día;
  - orden estricto de registro.
- **Notificaciones por correo** (registro, proximidad, llamado, cancelación) con reintentos.
- **Consulta pública del turno** desde el celular del trabajador (DNI + código, con datos enmascarados).
- **Importación del Excel institucional** con validación previa, vista previa y confirmación.
- **Reportes:** demanda, uso de cupos, inasistencia, tiempos de espera y de atención, y dependencias. Exportación a Excel o CSV según permisos.
- **Administración:** usuarios, roles y permisos, sedes y horarios, motivos, plantillas de correo y parámetros, sin tocar código.
- **Auditoría:** solo inserción, con cadena de hash verificable.

## Arquitectura

```
Navegador ──HTTPS:42000──> Caddy (interfaz React + proxy) ──> API FastAPI 127.0.0.1:42001 ──> PostgreSQL 16
```

| Capa | Tecnología |
|---|---|
| Frontend | React 19 · TypeScript · Vite · Tailwind · Radix UI · TanStack Query |
| Backend | Python 3.12 · FastAPI · SQLAlchemy 2 · Pydantic 2 · Alembic |
| Base de datos | PostgreSQL 16 (restricciones, triggers y auditoría encadenada) |
| Despliegue | Windows Server · servicios WinSW · Caddy (HTTPS) · tareas programadas de backup |

Es un monolito modular: sin microservicios, sin colas externas y sin dependencia de la nube. Funciona en la LAN sin Internet.

## Documentación

| Documento | Contenido |
|---|---|
| [01 · Análisis y diseño](docs/01-analisis-y-diseno.md) | Problema, supuestos, reglas de negocio, máquina de estados y decisiones |
| [02 · Modelo de datos](docs/02-modelo-datos.md) | Diagrama ER y diseño PostgreSQL |
| [03 · Diccionario de datos](docs/03-diccionario-datos.md) | Generado desde la base de datos |
| [04 · API REST](docs/04-api.md) | Endpoints, permisos y códigos de error |
| [05 · Despliegue](docs/05-despliegue.md) | Instalación en Windows Server, HTTPS, SMTP, actualización y solución de problemas |
| [06 · Backup y restauración](docs/06-backup-restauracion.md) | Estrategia, retención, verificación y recuperación ante desastres |
| [07 · Manual técnico](docs/07-manual-tecnico.md) | Arquitectura interna, seguridad, observabilidad y cómo extender |
| [08 · Manual de usuario](docs/08-manual-usuario.md) | Guía por rol, con capturas |
| [Base de datos](database/README.md) · [Backend](backend/README.md) · [Frontend](frontend/README.md) | Guías de cada componente |

## Inicio rápido

**Producción** (Windows Server, PowerShell como Administrador):

```powershell
git clone https://github.com/edergc/TopicoCSJLima.git; cd TopicoCSJLima
powershell -ExecutionPolicy Bypass -File database\bootstrap\bootstrap.ps1   # roles, bases de datos, .env
powershell -ExecutionPolicy Bypass -File deploy\windows\install.ps1         # servicios, HTTPS, backups
cd backend; .\.venv\Scripts\python -m app.cli create-admin --username admin --full-name "Nombre Apellido"
```

Acceso: `https://<servidor>:42000` · Diagnóstico: `deploy\windows\status.ps1`

**Desarrollo:** ver [backend/README.md](backend/README.md) y [frontend/README.md](frontend/README.md).

## Calidad

| Verificación | Cobertura |
|---|---|
| Pruebas de base de datos | Restricciones, triggers, privilegios, concurrencia real y auditoría |
| Pruebas de API | Flujos completos y los **7 casos críticos** del requerimiento (capacidad, cancelación, no presentado, concurrencia por el último cupo, alcance por sede, permisos, elegibilidad EPS) |
| Pruebas de frontend | Cliente HTTP, formato horario de Lima, componentes y formularios clave |
| Análisis estático | `ruff`, `mypy --strict`, `tsc` estricto, ESLint |
| Validación visual | Recorrido automatizado con capturas en escritorio, tablet y móvil |

```powershell
cd backend;  .\.venv\Scripts\python -m pytest     # 134 pruebas
cd frontend; npm test                               # 18 pruebas
```

## Estructura del repositorio

```
backend/     API FastAPI, migraciones, pruebas y CLI
frontend/    Interfaz React
database/    Bootstrap de PostgreSQL, DDL consolidado y guía
deploy/      Instalador, servicios, HTTPS y backups (Windows)
docs/        Documentación funcional, técnica y de usuario
```

## Pendientes conocidos

- **Histórico de atenciones:** su importación se habilitará al recibir el formato del Excel. El modelo de datos ya lo soporta.
- **Valores iniciales por confirmar con el área usuaria:** tolerancia de 10 minutos y horario de la sede Anselmo Barreto (hoy igual al de Alzamora). Se ajustan desde la aplicación.
- **Identidad visual:** aplicar el logotipo y los colores oficiales del Poder Judicial (tokens `--color-brand-*`).
