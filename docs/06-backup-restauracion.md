# Backup y restauración

## 1. Estrategia

| Aspecto | Definición |
|---|---|
| **Qué se respalda** | El esquema `topico` completo: datos, estructura, triggers, funciones y privilegios. Los roles y las extensiones los recrea `bootstrap.ps1`. |
| **Cómo** | `pg_dump` en formato custom comprimido. Cada archivo lleva su suma SHA-256 en un `.sha256` junto a él. |
| **Cuándo** | Diario a las 22:00 (tarea programada "TopicoCSJ - Backup diario"). |
| **Retención** | 14 diarios, 8 semanales (domingos) y 12 mensuales (el primer backup de cada mes). |
| **Validación inmediata** | Tras cada backup se comprueba que el archivo sea legible (`pg_restore --list`). |
| **Validación real** | Cada domingo a las 03:00 se **restaura** el último backup en la base aislada `topico_csj_verify` y se verifica el esquema, los conteos y la integridad de la auditoría. |
| **Pérdida máxima (RPO)** | 24 horas, con un backup diario. Si la institución requiere menos, ver la sección 6. |
| **Tiempo de recuperación (RTO)** | Minutos, según el volumen de datos. |

**Ubicación:** `TopicoCSJ-data\backups\{daily,weekly,monthly,pre-restore}\`.

> **Importante:** un backup en el mismo disco que la base de datos no protege ante la falla del disco ni ante un ransomware. Configure una **copia secundaria** en otro disco o en una carpeta de red institucional con el parámetro `-SecondaryPath`, editando la tarea programada (sección 4).

## 2. Backup manual

```powershell
powershell -ExecutionPolicy Bypass -File deploy\windows\backup\backup.ps1
# con copia secundaria:
powershell -ExecutionPolicy Bypass -File deploy\windows\backup\backup.ps1 -SecondaryPath \\servidor-archivos\backups\topico
```

El resultado queda en `logs\backup\backup-AAAA-MM.log` y en `backups\last-backup.json`, que también muestra `status.ps1`.

## 3. Verificar que los backups se pueden restaurar

```powershell
powershell -ExecutionPolicy Bypass -File deploy\windows\backup\verify-backup.ps1
```

El script:
1. Valida la suma SHA-256: detecta archivos dañados o alterados.
2. Restaura el backup en la base `topico_csj_verify`. **Nunca toca producción** y rechaza apuntar a ella.
3. Comprueba la versión del esquema, los conteos de atenciones, trabajadores y auditoría, y que la **cadena de auditoría esté íntegra**.
4. Borra la copia de prueba, para no conservar datos personales duplicados.

## 4. Configurar la tarea con copia secundaria

```powershell
$task = Get-ScheduledTask "TopicoCSJ - Backup diario"
$action = $task.Actions[0]
$action.Arguments += ' -SecondaryPath "\\servidor-archivos\backups\topico"'
Set-ScheduledTask -TaskName $task.TaskName -Action $action
```

La cuenta SYSTEM del servidor debe tener permiso de escritura en esa carpeta de red, a nivel de la cuenta del equipo en el dominio: `DOMINIO\SERVIDOR$`.

## 5. Restauración

### 5.1 En el mismo servidor (p. ej., recuperar datos tras un error grave)

```powershell
powershell -ExecutionPolicy Bypass -File deploy\windows\backup\restore.ps1 -DumpFile E:\PROGRAMACION\TopicoCSJ-data\backups\daily\topico_csj_20260929_220000.dump
```

Pide escribir `RESTAURAR topico_csj` como confirmación. Luego:
1. Valida la suma SHA-256 del backup.
2. **Detiene los servicios**, para que nadie escriba durante la restauración.
3. Toma un **backup de seguridad** del estado actual en `backups\pre-restore\`. Si no puede tomarlo, aborta sin cambiar nada.
4. **Aparta** el esquema actual (lo renombra), restaura el backup en una sola transacción y:
   - si la restauración falla, **devuelve automáticamente el esquema original**;
   - si tiene éxito, elimina el esquema apartado.
5. Aplica las migraciones pendientes, si el backup era de una versión anterior, y verifica la auditoría.
6. Inicia los servicios.

Todo queda registrado en `logs\backup\`. Informe la restauración al área correspondiente: las atenciones registradas después del backup se pierden.

### 5.2 En un servidor nuevo (desastre)

1. Instale PostgreSQL 16, Python 3.12 y Node 20.
2. Clone el repositorio y ejecute `database\bootstrap\bootstrap.ps1`.
3. Copie el backup (y su `.sha256`) al servidor.
4. Ejecute `deploy\windows\install.ps1`. Crea el esquema vacío.
5. Ejecute `deploy\windows\backup\restore.ps1 -DumpFile <backup>`.
6. Si antes se usaba la CA interna, distribuya el **nuevo** `root.crt` a los equipos cliente, o restaure la carpeta `TopicoCSJ-data\caddy\data` del servidor anterior para conservar el mismo certificado.

> Los secretos de `backend\.env` **no** forman parte del backup de la base. Tras un desastre se generan nuevos con `bootstrap.ps1`: las sesiones abiertas se invalidan (los usuarios vuelven a ingresar) y los datos no se ven afectados. Si se usa SMTP, reconfigure `SMTP_*`.

### 5.3 Restauración manual (sin scripts)

```powershell
$env:PGPASSWORD = "<clave de topico_owner>"
psql -h localhost -U topico_owner -d topico_csj -c "ALTER SCHEMA topico RENAME TO topico_prev"
pg_restore -h localhost -U topico_owner -d topico_csj --no-owner --role=topico_owner --exit-on-error --single-transaction <archivo.dump>
psql -h localhost -U topico_owner -d topico_csj -c "SELECT * FROM topico.verify_audit_chain()"   # 0 filas = íntegra
psql -h localhost -U topico_owner -d topico_csj -c "DROP SCHEMA topico_prev CASCADE"
```

## 6. Si se requiere menor pérdida de datos (RPO < 24 h)

Opciones, de menor a mayor complejidad:
1. **Backups más frecuentes:** agregue disparadores a la tarea programada (p. ej., 13:00 y 22:00).
2. **Archivado continuo de WAL (PITR)** en PostgreSQL (`archive_mode=on`, `archive_command`, backup base con `pg_basebackup`). Permite restaurar a un instante preciso, pero exige administración de PostgreSQL adicional.
3. **Réplica en caliente** en un segundo servidor (streaming replication).

## 7. Pruebas realizadas del procedimiento

Durante la construcción se verificó en este servidor:
- el backup (`backup.ps1`) con su suma y retención;
- la restauración de prueba (`verify-backup.ps1`) en una base aislada, con la auditoría íntegra;
- la restauración real (`restore.ps1 -Force`) con backup previo, apartado del esquema y verificación posterior.

Se recomienda repetir un **simulacro de restauración** trimestral siguiendo la sección 5.2 en un servidor de pruebas.
