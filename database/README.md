# Base de datos — Guía operativa

PostgreSQL 16 · base `topico_csj` · esquema `topico`.

| Recurso | Ubicación |
|---|---|
| Bootstrap (roles, BD, extensiones) | `database/bootstrap/` |
| Migraciones (fuente de verdad del DDL) | `backend/alembic/versions/` + `backend/alembic/sql/` |
| DDL consolidado (solo lectura, para revisión) | `database/schema.sql` |
| Diseño del modelo | `docs/02-modelo-datos.md` |
| Diccionario de datos (generado) | `docs/03-diccionario-datos.md` |
| Pruebas de integridad | `backend/tests/db/` |

## 1. Instalación inicial

```powershell
# 1) Roles, bases de datos y .env (pide la contraseña del superusuario postgres)
powershell -ExecutionPolicy Bypass -File database\bootstrap\bootstrap.ps1

# 2) Crear el esquema
cd backend
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\alembic current        # debe mostrar la última revisión con (head)
```

En Linux: exportar `TOPICO_OWNER_PASSWORD` y `TOPICO_APP_PASSWORD`, ejecutar
`psql -U postgres -v db_name=topico_csj -f database/bootstrap/bootstrap.sql` y completar `backend/.env` a mano.

> En Windows, si ve caracteres extraños en la consola, ejecute primero `$env:PYTHONUTF8=1`.

## 2. Migraciones

- **Nunca** modificar la BD a mano en producción. Todo cambio va en una nueva revisión de Alembic:
  1. Crear `backend/alembic/sql/000N_descripcion.up.sql` y `.down.sql`.
  2. Crear `backend/alembic/versions/000N_descripcion.py` que llame a `run_sql_file(...)`.
  3. **Otorgar explícitamente los privilegios** de las tablas nuevas a `topico_app` y `topico_readonly` (mínimo privilegio; no hay privilegios por defecto).
  4. Agregar `COMMENT ON` a tablas y columnas (lo exige una prueba).
  5. Ejecutar `pytest tests/db`, que valida upgrade → downgrade → upgrade.
  6. Regenerar la documentación:
     ```powershell
     .\.venv\Scripts\alembic upgrade head --sql > ..\database\schema.sql
     .\.venv\Scripts\python -m scripts.generate_data_dictionary
     ```
- Las revisiones base (`0001`, `0002`) nunca se revierten en producción.

## 3. Pruebas

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests/db -v
```

Usan la base `topico_csj_test`, que **se destruye y se recrea** en cada ejecución. Cubren: numeración de turnos, capacidad (casos críticos 1–4), máquina de estados, inmutabilidad, privilegios, concurrencia real con 12 conexiones simultáneas, y auditoría (cadena de hash y detección de alteraciones).

## 4. Consultas útiles de operación

```sql
-- Integridad de la auditoría (0 filas = íntegra)
SELECT * FROM topico.verify_audit_chain();

-- Consistencia de contadores del día (debe devolver 0 filas)
SELECT d.id, d.occupied_count, count(a.id) FILTER (WHERE s.consumes_capacity) AS real
  FROM topico.service_day d
  LEFT JOIN topico.appointment a ON a.service_day_id = d.id
  LEFT JOIN topico.appointment_status s ON s.code = a.status
 GROUP BY d.id HAVING d.occupied_count <> count(a.id) FILTER (WHERE s.consumes_capacity);

-- Configuración vigente por sede
SELECT DISTINCT ON (site_id) site_id, valid_from, daily_capacity, slot_minutes, tolerance_minutes
  FROM topico.site_setting_version WHERE valid_from <= current_date
 ORDER BY site_id, valid_from DESC;
```

## 5. Backup y restauración

Automatizados en `deploy/windows/backup/`: backup diario con retención, restauración de prueba semanal en la base aislada `topico_csj_verify` y restauración guiada. Ver **docs/06-backup-restauracion.md**. Procedimiento manual equivalente:

```powershell
# Backup completo (formato custom, comprimido), con el rol propietario
pg_dump -h localhost -U topico_owner -d topico_csj -Fc -f topico_csj_YYYYMMDD.dump

# Restauración de prueba en una base temporal (validación del backup)
createdb -h localhost -U postgres -O topico_owner topico_restore_check
pg_restore -h localhost -U postgres -d topico_restore_check --no-owner --role=topico_owner topico_csj_YYYYMMDD.dump
psql -h localhost -U postgres -d topico_restore_check -c "SELECT * FROM topico.verify_audit_chain();"
```
