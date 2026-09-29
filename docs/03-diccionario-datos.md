# Diccionario de datos — Tópico CSJ Lima

> Documento **generado automáticamente** desde el catálogo de PostgreSQL con
> `python -m scripts.generate_data_dictionary`. No editar a mano.

## Tablas

- [`app_user`](#app_user) — Usuarios del sistema (personal administrativo). No incluye a los trabajadores atendidos.
- [`appointment`](#appointment) — Solicitud de atención con turno. Registro administrativo: NO contiene información clínica. Nunca se elimina.
- [`appointment_event`](#appointment_event) — Historial inmutable de cambios de estado de cada atención (línea de tiempo).
- [`appointment_status`](#appointment_status) — Estados de la atención. Define qué estados ocupan cupo y cuáles son finales.
- [`appointment_status_transition`](#appointment_status_transition) — Máquina de estados: únicas transiciones permitidas. La BD rechaza cualquier otra.
- [`audit_event`](#audit_event) — Auditoría funcional. Solo inserción; cada fila encadena el hash de la anterior (detección de alteraciones).
- [`department`](#department) — Dependencias (órganos jurisdiccionales/administrativos) de la CSJ Lima.
- [`import_batch`](#import_batch) — Lote de importación de Excel. Flujo: UPLOADED → VALIDATED → CONFIRMED \| DISCARDED \| FAILED.
- [`import_row`](#import_row) — Filas en staging de un lote: dato crudo, dato normalizado, resultado de validación y diferencias.
- [`insurer`](#insurer) — Entidades prestadoras de salud (EPS). Inicialmente: RIMAC.
- [`notification`](#notification) — Bandeja de salida (outbox). Se inserta en la misma transacción del evento y un worker la procesa con reintentos.
- [`notification_template`](#notification_template) — Plantillas editables (Jinja2 con sandbox) por evento y canal.
- [`permission`](#permission) — Permisos atómicos (recurso:acción). Los define el código; la app solo los lee.
- [`reason`](#reason) — Motivos administrativos (cancelación, anulación, no presentado, devolución a cola). Nunca motivos clínicos.
- [`refresh_token`](#refresh_token) — Sesiones (refresh tokens rotativos). Solo se guarda el SHA-256 del token.
- [`role`](#role) — Roles: agrupaciones de permisos. is_system = rol base que no puede eliminarse.
- [`role_permission`](#role_permission) — Asignación de permisos a roles.
- [`service_day`](#service_day) — Día operativo por sede. Congela la configuración vigente y es el punto de serialización de registros (bloqueo de fila).
- [`site`](#site) — Sedes con tópico de atención (p. ej., Javier Alzamora Valdez, Anselmo Barreto).
- [`site_closure`](#site_closure) — Días en que el tópico de una sede no atiende (feriados, cierres).
- [`site_schedule`](#site_schedule) — Bloques de atención (mañana/tarde) por día de semana, con vigencia.
- [`site_setting_version`](#site_setting_version) — Configuración operativa por sede, versionada por fecha de vigencia. Se aplica la versión con mayor valid_from <= fecha.
- [`system_parameter`](#system_parameter) — Parámetros globales configurables sin modificar código.
- [`user_role`](#user_role) — Roles asignados a cada usuario.
- [`user_site`](#user_site) — Alcance por sede: un usuario solo opera las sedes asignadas aquí.
- [`worker`](#worker) — Trabajadores de la CSJ Lima (dato personal). Solo datos administrativos, sin información clínica.
- [`worker_coverage`](#worker_coverage) — Historial de habilitación EPS por trabajador. Vigente si valid_from <= fecha <= coalesce(valid_to, infinito).

## app_user

Usuarios del sistema (personal administrativo). No incluye a los trabajadores atendidos.

| Columna | Tipo | Nulo | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | bigint | no | IDENTITY |  |
| `public_id` | uuid | no | gen_random_uuid() | Identificador expuesto por la API (no enumerable). |
| `username` | character varying(50) | no |  | Nombre de usuario en minúsculas. En Fase 3 coincidirá con la cuenta AD/LDAP. |
| `full_name` | character varying(150) | no |  |  |
| `email` | character varying(254) | sí |  |  |
| `auth_provider` | character varying(10) | no | 'LOCAL'::character varying | LOCAL: contraseña propia (hash Argon2id). LDAP: autenticación institucional (Fase 3). |
| `password_hash` | character varying(255) | sí |  | Hash Argon2id. Nunca texto plano. NULL solo para LDAP. |
| `password_changed_at` | timestamp with time zone | sí |  |  |
| `must_change_password` | boolean | no | true |  |
| `is_active` | boolean | no | true |  |
| `failed_login_attempts` | smallint | no | 0 |  |
| `locked_until` | timestamp with time zone | sí |  | Bloqueo temporal por intentos fallidos consecutivos. |
| `last_login_at` | timestamp with time zone | sí |  |  |
| `created_at` | timestamp with time zone | no | now() |  |
| `updated_at` | timestamp with time zone | no | now() |  |
| `created_by` | bigint | sí |  |  |
| `updated_by` | bigint | sí |  |  |

**Restricciones**

| Nombre | Tipo | Definición |
|---|---|---|
| `app_user_pkey` | PK | `PRIMARY KEY (id)` |
| `uq_app_user_public_id` | UNIQUE | `UNIQUE (public_id)` |
| `uq_app_user_username` | UNIQUE | `UNIQUE (username)` |
| `app_user_created_by_fkey` | FK | `FOREIGN KEY (created_by) REFERENCES app_user(id)` |
| `app_user_updated_by_fkey` | FK | `FOREIGN KEY (updated_by) REFERENCES app_user(id)` |
| `ck_app_user_auth_provider` | CHECK | `CHECK (((auth_provider)::text = ANY ((ARRAY['LOCAL'::character varying, 'LDAP'::character varying])::text[])))` |
| `ck_app_user_email_format` | CHECK | `CHECK (((email IS NULL) OR ((email)::text ~* '^[^@\s]+@[^@\s]+\.[^@\s]+$'::text)))` |
| `ck_app_user_failed_attempts` | CHECK | `CHECK ((failed_login_attempts >= 0))` |
| `ck_app_user_full_name_not_blank` | CHECK | `CHECK ((btrim((full_name)::text) <> ''::text))` |
| `ck_app_user_local_password` | CHECK | `CHECK ((((auth_provider)::text <> 'LOCAL'::text) OR (password_hash IS NOT NULL)))` |
| `ck_app_user_username_format` | CHECK | `CHECK (((username)::text ~ '^[a-z0-9][a-z0-9._-]{2,49}$'::text))` |

**Triggers**

- `trg_app_user_updated_at` → `tg_set_updated_at()`

## appointment

Solicitud de atención con turno. Registro administrativo: NO contiene información clínica. Nunca se elimina.

| Columna | Tipo | Nulo | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | bigint | no | IDENTITY |  |
| `public_id` | uuid | no | gen_random_uuid() |  |
| `service_day_id` | bigint | no |  |  |
| `site_id` | integer | no |  | Desnormalizado desde service_day (lo asigna el trigger) para índices y reportes. |
| `service_date` | date | no |  | Fecha operativa (America/Lima). La asigna el trigger desde service_day. |
| `worker_id` | bigint | no |  |  |
| `ticket_number` | smallint | no |  | Correlativo por sede y día; lo asigna la BD. Define el orden de la cola. |
| `ticket_code` | character varying(8) | no |  | Código visible del turno: prefijo de la sede + número (A-009). |
| `status` | character varying(15) | no |  |  |
| `channel` | character varying(10) | no |  | Canal de la solicitud: PHONE, WALK_IN (presencial), WEB (Fase 2), MIGRATION (histórico). |
| `origin_appointment_id` | bigint | sí |  | Atención original cuando esta es una reprogramación. |
| `admin_note` | character varying(300) | sí |  | Observación ADMINISTRATIVA. Prohibido registrar síntomas, diagnósticos u otra información clínica. |
| `registered_at` | timestamp with time zone | no | now() |  |
| `registered_by` | bigint | no |  |  |
| `queued_at` | timestamp with time zone | sí |  | Momento en que la atención ingresó (o reingresó) a la cola EN_ESPERA. |
| `called_at` | timestamp with time zone | sí |  |  |
| `called_by` | bigint | sí |  |  |
| `call_count` | smallint | no | 0 | Número de veces que se llamó (incluye rellamados tras devolver a la cola). |
| `started_at` | timestamp with time zone | sí |  |  |
| `started_by` | bigint | sí |  |  |
| `finished_at` | timestamp with time zone | sí |  |  |
| `finished_by` | bigint | sí |  |  |
| `closed_at` | timestamp with time zone | sí |  | Momento de cancelación, no presentación o anulación. |
| `closed_by` | bigint | sí |  |  |
| `close_reason_id` | integer | sí |  |  |
| `close_note` | character varying(300) | sí |  |  |
| `version` | integer | no | 1 | Control de concurrencia optimista (lo gestiona el ORM). |
| `created_at` | timestamp with time zone | no | now() |  |
| `updated_at` | timestamp with time zone | no | now() |  |

**Restricciones**

| Nombre | Tipo | Definición |
|---|---|---|
| `appointment_pkey` | PK | `PRIMARY KEY (id)` |
| `uq_appointment_day_ticket` | UNIQUE | `UNIQUE (service_day_id, ticket_number)` |
| `uq_appointment_public_id` | UNIQUE | `UNIQUE (public_id)` |
| `appointment_called_by_fkey` | FK | `FOREIGN KEY (called_by) REFERENCES app_user(id)` |
| `appointment_close_reason_id_fkey` | FK | `FOREIGN KEY (close_reason_id) REFERENCES reason(id)` |
| `appointment_closed_by_fkey` | FK | `FOREIGN KEY (closed_by) REFERENCES app_user(id)` |
| `appointment_finished_by_fkey` | FK | `FOREIGN KEY (finished_by) REFERENCES app_user(id)` |
| `appointment_origin_appointment_id_fkey` | FK | `FOREIGN KEY (origin_appointment_id) REFERENCES appointment(id)` |
| `appointment_registered_by_fkey` | FK | `FOREIGN KEY (registered_by) REFERENCES app_user(id)` |
| `appointment_service_day_id_fkey` | FK | `FOREIGN KEY (service_day_id) REFERENCES service_day(id)` |
| `appointment_site_id_fkey` | FK | `FOREIGN KEY (site_id) REFERENCES site(id)` |
| `appointment_started_by_fkey` | FK | `FOREIGN KEY (started_by) REFERENCES app_user(id)` |
| `appointment_status_fkey` | FK | `FOREIGN KEY (status) REFERENCES appointment_status(code)` |
| `appointment_worker_id_fkey` | FK | `FOREIGN KEY (worker_id) REFERENCES worker(id)` |
| `ck_appointment_call_count` | CHECK | `CHECK ((call_count >= 0))` |
| `ck_appointment_called_data` | CHECK | `CHECK ((((status)::text <> ALL ((ARRAY['LLAMADO'::character varying, 'NO_PRESENTADO'::character varying])::text[])) OR ((channel)::text = 'MIGRATION'::text) OR ((called_at IS NOT NULL) AND (called_by IS NOT NULL))))` |
| `ck_appointment_channel` | CHECK | `CHECK (((channel)::text = ANY ((ARRAY['PHONE'::character varying, 'WALK_IN'::character varying, 'WEB'::character varying, 'MIGRATION'::character varying])::text[])))` |
| `ck_appointment_closed_data` | CHECK | `CHECK ((((status)::text <> ALL ((ARRAY['CANCELADO'::character varying, 'NO_PRESENTADO'::character varying, 'ANULADO'::character varying])::text[])) OR ((closed_at IS NOT NULL) AND (closed_by IS NOT NULL) AND ((close_reason_id IS NOT NULL) OR ((channel)::text = 'MIGRATION'::text)))))` |
| `ck_appointment_finished_data` | CHECK | `CHECK ((((status)::text <> 'ATENDIDO'::text) OR ((channel)::text = 'MIGRATION'::text) OR ((finished_at IS NOT NULL) AND (finished_by IS NOT NULL))))` |
| `ck_appointment_not_self_origin` | CHECK | `CHECK (((origin_appointment_id IS NULL) OR (origin_appointment_id <> id)))` |
| `ck_appointment_started_data` | CHECK | `CHECK ((((status)::text <> ALL ((ARRAY['EN_ATENCION'::character varying, 'ATENDIDO'::character varying])::text[])) OR ((channel)::text = 'MIGRATION'::text) OR ((started_at IS NOT NULL) AND (started_by IS NOT NULL))))` |
| `ck_appointment_ticket` | CHECK | `CHECK (((ticket_number > 0) AND ((ticket_code)::text ~ '^[A-Z]{1,3}-[0-9]{3}$'::text)))` |
| `ck_appointment_time_order` | CHECK | `CHECK ((((called_at IS NULL) OR (called_at >= registered_at)) AND ((started_at IS NULL) OR (started_at >= registered_at)) AND ((finished_at IS NULL) OR (started_at IS NULL) OR (finished_at >= started_at)) AND ((closed_at IS NULL) OR (closed_at >= registered_at))))` |
| `ck_appointment_version` | CHECK | `CHECK ((version > 0))` |

**Índices adicionales**

- `ix_appointment_close_reason`: `CREATE INDEX ix_appointment_close_reason ON topico.appointment USING btree (close_reason_id) WHERE (close_reason_id IS NOT NULL)`
- `ix_appointment_origin`: `CREATE INDEX ix_appointment_origin ON topico.appointment USING btree (origin_appointment_id) WHERE (origin_appointment_id IS NOT NULL)`
- `ix_appointment_queue`: `CREATE INDEX ix_appointment_queue ON topico.appointment USING btree (service_day_id, status, ticket_number)`
- `ix_appointment_site_date`: `CREATE INDEX ix_appointment_site_date ON topico.appointment USING btree (site_id, service_date)`
- `ix_appointment_worker_date`: `CREATE INDEX ix_appointment_worker_date ON topico.appointment USING btree (worker_id, service_date DESC)`
- `uq_appointment_worker_active_day`: `CREATE UNIQUE INDEX uq_appointment_worker_active_day ON topico.appointment USING btree (worker_id, service_date) WHERE ((status)::text = ANY ((ARRAY['REGISTRADO'::character varying, 'EN_ESPERA'::character varying, 'LLAMADO'::character varying, 'EN_ATENCION'::character varying])::text[]))`

**Triggers**

- `trg_appointment_before_insert` → `tg_appointment_before_insert()`
- `trg_appointment_before_update` → `tg_appointment_before_update()`
- `trg_appointment_forbid_delete` → `tg_forbid_change()`
- `trg_appointment_forbid_truncate` → `tg_forbid_change()`

## appointment_event

Historial inmutable de cambios de estado de cada atención (línea de tiempo).

| Columna | Tipo | Nulo | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | bigint | no | IDENTITY |  |
| `appointment_id` | bigint | no |  |  |
| `action` | character varying(20) | no |  |  |
| `from_status` | character varying(15) | sí |  |  |
| `to_status` | character varying(15) | no |  |  |
| `reason_id` | integer | sí |  |  |
| `note` | character varying(300) | sí |  |  |
| `occurred_at` | timestamp with time zone | no | now() |  |
| `user_id` | bigint | sí |  | Usuario que ejecutó la acción; NULL para acciones automáticas del sistema. |
| `ip` | inet | sí |  |  |
| `request_id` | character varying(40) | sí |  |  |

**Restricciones**

| Nombre | Tipo | Definición |
|---|---|---|
| `appointment_event_pkey` | PK | `PRIMARY KEY (id)` |
| `appointment_event_appointment_id_fkey` | FK | `FOREIGN KEY (appointment_id) REFERENCES appointment(id)` |
| `appointment_event_from_status_fkey` | FK | `FOREIGN KEY (from_status) REFERENCES appointment_status(code)` |
| `appointment_event_reason_id_fkey` | FK | `FOREIGN KEY (reason_id) REFERENCES reason(id)` |
| `appointment_event_to_status_fkey` | FK | `FOREIGN KEY (to_status) REFERENCES appointment_status(code)` |
| `appointment_event_user_id_fkey` | FK | `FOREIGN KEY (user_id) REFERENCES app_user(id)` |
| `ck_appointment_event_action` | CHECK | `CHECK (((action)::text = ANY ((ARRAY['REGISTER'::character varying, 'ACTIVATE'::character varying, 'CALL'::character varying, 'REQUEUE'::character varying, 'START'::character varying, 'FINISH'::character varying, 'CANCEL'::character varying, 'NO_SHOW'::character varying, 'VOID'::character varying, 'MIGRATE'::character varying])::text[])))` |
| `ck_appointment_event_from` | CHECK | `CHECK ((((action)::text = ANY ((ARRAY['REGISTER'::character varying, 'MIGRATE'::character varying])::text[])) = (from_status IS NULL)))` |

**Índices adicionales**

- `ix_appointment_event_appointment`: `CREATE INDEX ix_appointment_event_appointment ON topico.appointment_event USING btree (appointment_id, occurred_at)`
- `ix_appointment_event_occurred`: `CREATE INDEX ix_appointment_event_occurred ON topico.appointment_event USING btree (occurred_at)`

**Triggers**

- `trg_appointment_event_forbid_change` → `tg_forbid_change()`
- `trg_appointment_event_forbid_truncate` → `tg_forbid_change()`

## appointment_status

Estados de la atención. Define qué estados ocupan cupo y cuáles son finales.

| Columna | Tipo | Nulo | Por defecto | Descripción |
|---|---|---|---|---|
| `code` | character varying(15) | no |  |  |
| `label` | character varying(40) | no |  |  |
| `description` | character varying(200) | no |  |  |
| `consumes_capacity` | boolean | no |  | true: la atención ocupa un cupo del día en este estado. |
| `is_final` | boolean | no |  |  |
| `is_active_queue` | boolean | no |  | true: la atención está viva (cuenta para la regla "una atención activa por trabajador y día"). |
| `sort_order` | smallint | no |  |  |

**Restricciones**

| Nombre | Tipo | Definición |
|---|---|---|
| `appointment_status_pkey` | PK | `PRIMARY KEY (code)` |
| `ck_appointment_status_final` | CHECK | `CHECK ((NOT (is_final AND is_active_queue)))` |

## appointment_status_transition

Máquina de estados: únicas transiciones permitidas. La BD rechaza cualquier otra.

| Columna | Tipo | Nulo | Por defecto | Descripción |
|---|---|---|---|---|
| `from_status` | character varying(15) | no |  |  |
| `to_status` | character varying(15) | no |  |  |
| `action` | character varying(20) | no |  |  |

**Restricciones**

| Nombre | Tipo | Definición |
|---|---|---|
| `pk_appointment_status_transition` | PK | `PRIMARY KEY (from_status, to_status)` |
| `appointment_status_transition_from_status_fkey` | FK | `FOREIGN KEY (from_status) REFERENCES appointment_status(code)` |
| `appointment_status_transition_to_status_fkey` | FK | `FOREIGN KEY (to_status) REFERENCES appointment_status(code)` |
| `ck_appointment_status_transition_distinct` | CHECK | `CHECK (((from_status)::text <> (to_status)::text))` |

## audit_event

Auditoría funcional. Solo inserción; cada fila encadena el hash de la anterior (detección de alteraciones).

| Columna | Tipo | Nulo | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | bigint | no | IDENTITY |  |
| `chain_seq` | bigint | no |  | Posición en la cadena de hash (sin huecos). La asigna el trigger bajo bloqueo. |
| `occurred_at` | timestamp with time zone | no | clock_timestamp() |  |
| `user_id` | bigint | sí |  |  |
| `username` | character varying(50) | sí |  | Copia del usuario al momento del evento (se conserva aunque el usuario cambie). |
| `ip` | inet | sí |  |  |
| `user_agent` | character varying(500) | sí |  |  |
| `request_id` | character varying(40) | sí |  |  |
| `action` | character varying(60) | no |  |  |
| `resource_type` | character varying(40) | sí |  |  |
| `resource_id` | character varying(64) | sí |  |  |
| `site_id` | integer | sí |  |  |
| `result` | character varying(10) | no |  |  |
| `reason` | character varying(500) | sí |  |  |
| `before_data` | jsonb | sí |  | Valores anteriores (solo campos relevantes; nunca contraseñas ni tokens). |
| `after_data` | jsonb | sí |  |  |
| `metadata` | jsonb | sí |  |  |
| `prev_hash` | character(64) | sí |  |  |
| `hash` | character(64) | no |  | SHA-256 del contenido del evento + prev_hash. |

**Restricciones**

| Nombre | Tipo | Definición |
|---|---|---|
| `audit_event_pkey` | PK | `PRIMARY KEY (id)` |
| `uq_audit_event_chain_seq` | UNIQUE | `UNIQUE (chain_seq)` |
| `audit_event_site_id_fkey` | FK | `FOREIGN KEY (site_id) REFERENCES site(id)` |
| `audit_event_user_id_fkey` | FK | `FOREIGN KEY (user_id) REFERENCES app_user(id)` |
| `ck_audit_event_action_format` | CHECK | `CHECK (((action)::text ~ '^[A-Z][A-Z0-9_]{2,59}$'::text))` |
| `ck_audit_event_hash_format` | CHECK | `CHECK ((hash ~ '^[0-9a-f]{64}$'::text))` |
| `ck_audit_event_result` | CHECK | `CHECK (((result)::text = ANY ((ARRAY['SUCCESS'::character varying, 'DENIED'::character varying, 'FAILURE'::character varying])::text[])))` |

**Índices adicionales**

- `ix_audit_event_action`: `CREATE INDEX ix_audit_event_action ON topico.audit_event USING btree (action, occurred_at DESC)`
- `ix_audit_event_occurred`: `CREATE INDEX ix_audit_event_occurred ON topico.audit_event USING btree (occurred_at DESC)`
- `ix_audit_event_resource`: `CREATE INDEX ix_audit_event_resource ON topico.audit_event USING btree (resource_type, resource_id)`
- `ix_audit_event_user`: `CREATE INDEX ix_audit_event_user ON topico.audit_event USING btree (user_id, occurred_at DESC)`

**Triggers**

- `trg_audit_event_before_insert` → `tg_audit_event_before_insert()`
- `trg_audit_event_forbid_change` → `tg_forbid_change()`
- `trg_audit_event_forbid_truncate` → `tg_forbid_change()`

## department

Dependencias (órganos jurisdiccionales/administrativos) de la CSJ Lima.

| Columna | Tipo | Nulo | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | integer | no | IDENTITY |  |
| `code` | character varying(30) | sí |  |  |
| `name` | character varying(200) | no |  |  |
| `normalized_name` | character varying(200) | no |  | Nombre en mayúsculas, sin tildes ni espacios repetidos; evita duplicados al importar. |
| `is_active` | boolean | no | true |  |
| `created_at` | timestamp with time zone | no | now() |  |
| `updated_at` | timestamp with time zone | no | now() |  |

**Restricciones**

| Nombre | Tipo | Definición |
|---|---|---|
| `department_pkey` | PK | `PRIMARY KEY (id)` |
| `uq_department_code` | UNIQUE | `UNIQUE (code)` |
| `uq_department_normalized_name` | UNIQUE | `UNIQUE (normalized_name)` |
| `ck_department_name_not_blank` | CHECK | `CHECK ((btrim((name)::text) <> ''::text))` |

**Triggers**

- `trg_department_updated_at` → `tg_set_updated_at()`

## import_batch

Lote de importación de Excel. Flujo: UPLOADED → VALIDATED → CONFIRMED \| DISCARDED \| FAILED.

| Columna | Tipo | Nulo | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | bigint | no | IDENTITY |  |
| `public_id` | uuid | no | gen_random_uuid() |  |
| `kind` | character varying(30) | no |  |  |
| `status` | character varying(12) | no | 'UPLOADED'::character varying |  |
| `file_name` | character varying(255) | no |  |  |
| `file_sha256` | character(64) | no |  | Huella del archivo; evita reimportar el mismo contenido. |
| `file_size_bytes` | integer | no |  |  |
| `sheet_name` | character varying(100) | sí |  |  |
| `options` | jsonb | no | '{}'::jsonb | Opciones elegidas al confirmar (p. ej., dar de baja la cobertura de los ausentes). |
| `column_mapping` | jsonb | sí |  |  |
| `total_rows` | integer | no | 0 |  |
| `new_count` | integer | no | 0 |  |
| `update_count` | integer | no | 0 |  |
| `unchanged_count` | integer | no | 0 |  |
| `error_count` | integer | no | 0 |  |
| `duplicate_count` | integer | no | 0 |  |
| `deactivated_count` | integer | no | 0 |  |
| `failure_message` | character varying(1000) | sí |  |  |
| `created_at` | timestamp with time zone | no | now() |  |
| `created_by` | bigint | no |  |  |
| `validated_at` | timestamp with time zone | sí |  |  |
| `confirmed_at` | timestamp with time zone | sí |  |  |
| `confirmed_by` | bigint | sí |  |  |
| `discarded_at` | timestamp with time zone | sí |  |  |
| `discarded_by` | bigint | sí |  |  |
| `updated_at` | timestamp with time zone | no | now() |  |

**Restricciones**

| Nombre | Tipo | Definición |
|---|---|---|
| `import_batch_pkey` | PK | `PRIMARY KEY (id)` |
| `uq_import_batch_public_id` | UNIQUE | `UNIQUE (public_id)` |
| `import_batch_confirmed_by_fkey` | FK | `FOREIGN KEY (confirmed_by) REFERENCES app_user(id)` |
| `import_batch_created_by_fkey` | FK | `FOREIGN KEY (created_by) REFERENCES app_user(id)` |
| `import_batch_discarded_by_fkey` | FK | `FOREIGN KEY (discarded_by) REFERENCES app_user(id)` |
| `ck_import_batch_confirmed` | CHECK | `CHECK ((((status)::text <> 'CONFIRMED'::text) OR ((confirmed_at IS NOT NULL) AND (confirmed_by IS NOT NULL))))` |
| `ck_import_batch_counts` | CHECK | `CHECK (((total_rows >= 0) AND (new_count >= 0) AND (update_count >= 0) AND (unchanged_count >= 0) AND (error_count >= 0) AND (duplicate_count >= 0) AND (deactivated_count >= 0)))` |
| `ck_import_batch_discarded` | CHECK | `CHECK ((((status)::text <> 'DISCARDED'::text) OR ((discarded_at IS NOT NULL) AND (discarded_by IS NOT NULL))))` |
| `ck_import_batch_kind` | CHECK | `CHECK (((kind)::text = ANY ((ARRAY['WORKERS_EPS'::character varying, 'HISTORICAL_APPOINTMENTS'::character varying])::text[])))` |
| `ck_import_batch_sha256` | CHECK | `CHECK ((file_sha256 ~ '^[0-9a-f]{64}$'::text))` |
| `ck_import_batch_size` | CHECK | `CHECK ((file_size_bytes > 0))` |
| `ck_import_batch_status` | CHECK | `CHECK (((status)::text = ANY ((ARRAY['UPLOADED'::character varying, 'VALIDATED'::character varying, 'CONFIRMED'::character varying, 'DISCARDED'::character varying, 'FAILED'::character varying])::text[])))` |

**Índices adicionales**

- `ix_import_batch_created`: `CREATE INDEX ix_import_batch_created ON topico.import_batch USING btree (created_at DESC)`
- `uq_import_batch_confirmed_file`: `CREATE UNIQUE INDEX uq_import_batch_confirmed_file ON topico.import_batch USING btree (kind, file_sha256) WHERE ((status)::text = 'CONFIRMED'::text)`

**Triggers**

- `trg_import_batch_updated_at` → `tg_set_updated_at()`

## import_row

Filas en staging de un lote: dato crudo, dato normalizado, resultado de validación y diferencias.

| Columna | Tipo | Nulo | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | bigint | no | IDENTITY |  |
| `batch_id` | bigint | no |  |  |
| `row_number` | integer | no |  | Número de fila en la hoja de Excel (para que el usuario ubique el error). |
| `raw` | jsonb | no |  |  |
| `normalized` | jsonb | sí |  |  |
| `outcome` | character varying(20) | no |  |  |
| `errors` | jsonb | no | '[]'::jsonb |  |
| `warnings` | jsonb | no | '[]'::jsonb |  |
| `changes` | jsonb | sí |  | Diferencias campo a campo {campo: [anterior, nuevo]} cuando outcome = UPDATE. |
| `target_worker_id` | bigint | sí |  |  |
| `created_at` | timestamp with time zone | no | now() |  |

**Restricciones**

| Nombre | Tipo | Definición |
|---|---|---|
| `import_row_pkey` | PK | `PRIMARY KEY (id)` |
| `uq_import_row_batch_row` | UNIQUE | `UNIQUE (batch_id, row_number)` |
| `import_row_batch_id_fkey` | FK | `FOREIGN KEY (batch_id) REFERENCES import_batch(id)` |
| `import_row_target_worker_id_fkey` | FK | `FOREIGN KEY (target_worker_id) REFERENCES worker(id)` |
| `ck_import_row_error_has_messages` | CHECK | `CHECK ((((outcome)::text <> 'ERROR'::text) OR (jsonb_array_length(errors) > 0)))` |
| `ck_import_row_errors_array` | CHECK | `CHECK (((jsonb_typeof(errors) = 'array'::text) AND (jsonb_typeof(warnings) = 'array'::text)))` |
| `ck_import_row_number` | CHECK | `CHECK ((row_number > 0))` |
| `ck_import_row_outcome` | CHECK | `CHECK (((outcome)::text = ANY ((ARRAY['NEW'::character varying, 'UPDATE'::character varying, 'UNCHANGED'::character varying, 'ERROR'::character varying, 'DUPLICATE_IN_FILE'::character varying])::text[])))` |

**Índices adicionales**

- `ix_import_row_batch_outcome`: `CREATE INDEX ix_import_row_batch_outcome ON topico.import_row USING btree (batch_id, outcome)`

## insurer

Entidades prestadoras de salud (EPS). Inicialmente: RIMAC.

| Columna | Tipo | Nulo | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | integer | no | IDENTITY |  |
| `code` | character varying(20) | no |  |  |
| `name` | character varying(120) | no |  |  |
| `is_active` | boolean | no | true |  |
| `created_at` | timestamp with time zone | no | now() |  |

**Restricciones**

| Nombre | Tipo | Definición |
|---|---|---|
| `insurer_pkey` | PK | `PRIMARY KEY (id)` |
| `uq_insurer_code` | UNIQUE | `UNIQUE (code)` |
| `ck_insurer_code_format` | CHECK | `CHECK (((code)::text ~ '^[A-Z][A-Z0-9_]{1,19}$'::text))` |

## notification

Bandeja de salida (outbox). Se inserta en la misma transacción del evento y un worker la procesa con reintentos.

| Columna | Tipo | Nulo | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | bigint | no | IDENTITY |  |
| `appointment_id` | bigint | sí |  |  |
| `template_code` | character varying(40) | no |  |  |
| `channel` | character varying(10) | no |  |  |
| `recipient` | character varying(254) | sí |  |  |
| `subject` | character varying(200) | sí |  |  |
| `body_text` | text | sí |  |  |
| `body_html` | text | sí |  |  |
| `status` | character varying(10) | no | 'PENDING'::character varying | SKIPPED: no se envía (p. ej., el trabajador no tiene correo). FAILED: agotó reintentos. |
| `attempts` | smallint | no | 0 |  |
| `max_attempts` | smallint | no | 5 |  |
| `next_attempt_at` | timestamp with time zone | no | now() |  |
| `last_error` | character varying(1000) | sí |  |  |
| `dedup_key` | character varying(120) | sí |  | Evita notificaciones duplicadas del mismo evento (p. ej., APPT_UPCOMING:<id>). |
| `sent_at` | timestamp with time zone | sí |  |  |
| `created_at` | timestamp with time zone | no | now() |  |
| `updated_at` | timestamp with time zone | no | now() |  |
| `created_by` | bigint | sí |  |  |

**Restricciones**

| Nombre | Tipo | Definición |
|---|---|---|
| `notification_pkey` | PK | `PRIMARY KEY (id)` |
| `uq_notification_dedup_key` | UNIQUE | `UNIQUE (dedup_key)` |
| `notification_appointment_id_fkey` | FK | `FOREIGN KEY (appointment_id) REFERENCES appointment(id)` |
| `notification_created_by_fkey` | FK | `FOREIGN KEY (created_by) REFERENCES app_user(id)` |
| `ck_notification_attempts` | CHECK | `CHECK (((attempts >= 0) AND ((max_attempts >= 1) AND (max_attempts <= 20)) AND (attempts <= max_attempts)))` |
| `ck_notification_channel` | CHECK | `CHECK (((channel)::text = 'EMAIL'::text))` |
| `ck_notification_recipient` | CHECK | `CHECK ((((status)::text = ANY ((ARRAY['SKIPPED'::character varying, 'CANCELLED'::character varying])::text[])) OR (recipient IS NOT NULL)))` |
| `ck_notification_sent` | CHECK | `CHECK ((((status)::text <> 'SENT'::text) OR (sent_at IS NOT NULL)))` |
| `ck_notification_status` | CHECK | `CHECK (((status)::text = ANY ((ARRAY['PENDING'::character varying, 'SENDING'::character varying, 'SENT'::character varying, 'FAILED'::character varying, 'SKIPPED'::character varying, 'CANCELLED'::character varying])::text[])))` |

**Índices adicionales**

- `ix_notification_appointment`: `CREATE INDEX ix_notification_appointment ON topico.notification USING btree (appointment_id)`
- `ix_notification_pending`: `CREATE INDEX ix_notification_pending ON topico.notification USING btree (next_attempt_at) WHERE ((status)::text = 'PENDING'::text)`
- `ix_notification_status_created`: `CREATE INDEX ix_notification_status_created ON topico.notification USING btree (status, created_at DESC)`

**Triggers**

- `trg_notification_updated_at` → `tg_set_updated_at()`

## notification_template

Plantillas editables (Jinja2 con sandbox) por evento y canal.

| Columna | Tipo | Nulo | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | integer | no | IDENTITY |  |
| `code` | character varying(40) | no |  |  |
| `channel` | character varying(10) | no | 'EMAIL'::character varying |  |
| `description` | character varying(200) | no |  |  |
| `subject` | character varying(200) | no |  |  |
| `body_text` | text | no |  |  |
| `body_html` | text | sí |  |  |
| `is_active` | boolean | no | true |  |
| `created_at` | timestamp with time zone | no | now() |  |
| `updated_at` | timestamp with time zone | no | now() |  |
| `updated_by` | bigint | sí |  |  |

**Restricciones**

| Nombre | Tipo | Definición |
|---|---|---|
| `notification_template_pkey` | PK | `PRIMARY KEY (id)` |
| `uq_notification_template_code_channel` | UNIQUE | `UNIQUE (code, channel)` |
| `notification_template_updated_by_fkey` | FK | `FOREIGN KEY (updated_by) REFERENCES app_user(id)` |
| `ck_notification_template_channel` | CHECK | `CHECK (((channel)::text = 'EMAIL'::text))` |
| `ck_notification_template_code_format` | CHECK | `CHECK (((code)::text ~ '^[A-Z][A-Z0-9_]{1,39}$'::text))` |

**Triggers**

- `trg_notification_template_updated_at` → `tg_set_updated_at()`

## permission

Permisos atómicos (recurso:acción). Los define el código; la app solo los lee.

| Columna | Tipo | Nulo | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | integer | no | IDENTITY |  |
| `code` | character varying(60) | no |  |  |
| `module` | character varying(30) | no |  |  |
| `description` | character varying(300) | no |  |  |

**Restricciones**

| Nombre | Tipo | Definición |
|---|---|---|
| `permission_pkey` | PK | `PRIMARY KEY (id)` |
| `uq_permission_code` | UNIQUE | `UNIQUE (code)` |
| `ck_permission_code_format` | CHECK | `CHECK (((code)::text ~ '^[a-z_]+:[a-z_]+$'::text))` |

## reason

Motivos administrativos (cancelación, anulación, no presentado, devolución a cola). Nunca motivos clínicos.

| Columna | Tipo | Nulo | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | integer | no | IDENTITY |  |
| `type` | character varying(15) | no |  |  |
| `code` | character varying(40) | no |  |  |
| `label` | character varying(150) | no |  |  |
| `requires_note` | boolean | no | false | Si es true, la acción exige una observación (p. ej., motivo "Otro"). |
| `is_active` | boolean | no | true |  |
| `sort_order` | smallint | no | 0 |  |
| `created_at` | timestamp with time zone | no | now() |  |
| `updated_at` | timestamp with time zone | no | now() |  |
| `updated_by` | bigint | sí |  |  |

**Restricciones**

| Nombre | Tipo | Definición |
|---|---|---|
| `reason_pkey` | PK | `PRIMARY KEY (id)` |
| `uq_reason_type_code` | UNIQUE | `UNIQUE (type, code)` |
| `reason_updated_by_fkey` | FK | `FOREIGN KEY (updated_by) REFERENCES app_user(id)` |
| `ck_reason_code_format` | CHECK | `CHECK (((code)::text ~ '^[A-Z][A-Z0-9_]{1,39}$'::text))` |
| `ck_reason_type` | CHECK | `CHECK (((type)::text = ANY ((ARRAY['CANCEL'::character varying, 'VOID'::character varying, 'NO_SHOW'::character varying, 'REQUEUE'::character varying])::text[])))` |

**Triggers**

- `trg_reason_updated_at` → `tg_set_updated_at()`

## refresh_token

Sesiones (refresh tokens rotativos). Solo se guarda el SHA-256 del token.

| Columna | Tipo | Nulo | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | bigint | no | IDENTITY |  |
| `user_id` | bigint | no |  |  |
| `family_id` | uuid | no |  | Cadena de rotación. Si se reutiliza un token ya rotado, se revoca toda la familia. |
| `token_hash` | character(64) | no |  |  |
| `issued_at` | timestamp with time zone | no | now() |  |
| `expires_at` | timestamp with time zone | no |  |  |
| `revoked_at` | timestamp with time zone | sí |  |  |
| `revoked_reason` | character varying(30) | sí |  |  |
| `replaced_by_id` | bigint | sí |  |  |
| `ip` | inet | sí |  |  |
| `user_agent` | character varying(500) | sí |  |  |

**Restricciones**

| Nombre | Tipo | Definición |
|---|---|---|
| `refresh_token_pkey` | PK | `PRIMARY KEY (id)` |
| `uq_refresh_token_hash` | UNIQUE | `UNIQUE (token_hash)` |
| `refresh_token_replaced_by_id_fkey` | FK | `FOREIGN KEY (replaced_by_id) REFERENCES refresh_token(id)` |
| `refresh_token_user_id_fkey` | FK | `FOREIGN KEY (user_id) REFERENCES app_user(id)` |
| `ck_refresh_token_expiry` | CHECK | `CHECK ((expires_at > issued_at))` |
| `ck_refresh_token_hash_format` | CHECK | `CHECK ((token_hash ~ '^[0-9a-f]{64}$'::text))` |
| `ck_refresh_token_revoked_reason` | CHECK | `CHECK (((revoked_reason IS NULL) OR ((revoked_reason)::text = ANY ((ARRAY['ROTATED'::character varying, 'LOGOUT'::character varying, 'REUSE_DETECTED'::character varying, 'ADMIN'::character varying, 'PASSWORD_CHANGED'::character varying])::text[]))))` |

**Índices adicionales**

- `ix_refresh_token_family`: `CREATE INDEX ix_refresh_token_family ON topico.refresh_token USING btree (family_id)`
- `ix_refresh_token_user`: `CREATE INDEX ix_refresh_token_user ON topico.refresh_token USING btree (user_id)`

## role

Roles: agrupaciones de permisos. is_system = rol base que no puede eliminarse.

| Columna | Tipo | Nulo | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | integer | no | IDENTITY |  |
| `code` | character varying(30) | no |  |  |
| `name` | character varying(80) | no |  |  |
| `description` | character varying(300) | sí |  |  |
| `is_system` | boolean | no | false |  |
| `is_active` | boolean | no | true |  |
| `created_at` | timestamp with time zone | no | now() |  |
| `updated_at` | timestamp with time zone | no | now() |  |

**Restricciones**

| Nombre | Tipo | Definición |
|---|---|---|
| `role_pkey` | PK | `PRIMARY KEY (id)` |
| `uq_role_code` | UNIQUE | `UNIQUE (code)` |
| `ck_role_code_format` | CHECK | `CHECK (((code)::text ~ '^[A-Z][A-Z0-9_]{1,29}$'::text))` |

**Triggers**

- `trg_role_updated_at` → `tg_set_updated_at()`

## role_permission

Asignación de permisos a roles.

| Columna | Tipo | Nulo | Por defecto | Descripción |
|---|---|---|---|---|
| `role_id` | integer | no |  |  |
| `permission_id` | integer | no |  |  |
| `created_at` | timestamp with time zone | no | now() |  |
| `created_by` | bigint | sí |  |  |

**Restricciones**

| Nombre | Tipo | Definición |
|---|---|---|
| `pk_role_permission` | PK | `PRIMARY KEY (role_id, permission_id)` |
| `role_permission_created_by_fkey` | FK | `FOREIGN KEY (created_by) REFERENCES app_user(id)` |
| `role_permission_permission_id_fkey` | FK | `FOREIGN KEY (permission_id) REFERENCES permission(id)` |
| `role_permission_role_id_fkey` | FK | `FOREIGN KEY (role_id) REFERENCES role(id)` |

**Índices adicionales**

- `ix_role_permission_permission`: `CREATE INDEX ix_role_permission_permission ON topico.role_permission USING btree (permission_id)`

## service_day

Día operativo por sede. Congela la configuración vigente y es el punto de serialización de registros (bloqueo de fila).

| Columna | Tipo | Nulo | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | bigint | no | IDENTITY |  |
| `site_id` | integer | no |  |  |
| `service_date` | date | no |  |  |
| `setting_version_id` | bigint | no |  |  |
| `status` | character varying(6) | no | 'OPEN'::character varying |  |
| `capacity` | smallint | no |  | Capacidad congelada al abrir el día; solo cambia por ajuste explícito y auditado. |
| `slot_minutes` | smallint | no |  |  |
| `tolerance_minutes` | smallint | no |  |  |
| `max_concurrent_in_service` | smallint | no |  |  |
| `occupied_count` | smallint | no | 0 | Cupos ocupados. Lo mantienen los triggers de appointment; la aplicación no puede escribirlo. |
| `last_ticket_number` | smallint | no | 0 | Último número de turno emitido (correlativo sin reutilización). Lo mantiene un trigger. |
| `opened_at` | timestamp with time zone | no | now() |  |
| `closed_at` | timestamp with time zone | sí |  |  |
| `closed_by` | bigint | sí |  |  |
| `capacity_adjusted_at` | timestamp with time zone | sí |  |  |
| `capacity_adjusted_by` | bigint | sí |  |  |
| `capacity_adjust_reason` | character varying(300) | sí |  |  |
| `created_at` | timestamp with time zone | no | now() |  |
| `updated_at` | timestamp with time zone | no | now() |  |

**Restricciones**

| Nombre | Tipo | Definición |
|---|---|---|
| `service_day_pkey` | PK | `PRIMARY KEY (id)` |
| `uq_service_day_site_date` | UNIQUE | `UNIQUE (site_id, service_date)` |
| `service_day_capacity_adjusted_by_fkey` | FK | `FOREIGN KEY (capacity_adjusted_by) REFERENCES app_user(id)` |
| `service_day_closed_by_fkey` | FK | `FOREIGN KEY (closed_by) REFERENCES app_user(id)` |
| `service_day_setting_version_id_fkey` | FK | `FOREIGN KEY (setting_version_id) REFERENCES site_setting_version(id)` |
| `service_day_site_id_fkey` | FK | `FOREIGN KEY (site_id) REFERENCES site(id)` |
| `ck_service_day_adjust` | CHECK | `CHECK (((capacity_adjusted_at IS NULL) OR ((capacity_adjusted_by IS NOT NULL) AND (capacity_adjust_reason IS NOT NULL))))` |
| `ck_service_day_capacity` | CHECK | `CHECK (((occupied_count >= 0) AND (occupied_count <= capacity)))` |
| `ck_service_day_capacity_range` | CHECK | `CHECK (((capacity >= 0) AND (capacity <= 500)))` |
| `ck_service_day_closed` | CHECK | `CHECK ((((status)::text <> 'CLOSED'::text) OR (closed_at IS NOT NULL)))` |
| `ck_service_day_concurrent` | CHECK | `CHECK (((max_concurrent_in_service >= 1) AND (max_concurrent_in_service <= 10)))` |
| `ck_service_day_slot` | CHECK | `CHECK (((slot_minutes >= 5) AND (slot_minutes <= 120)))` |
| `ck_service_day_status` | CHECK | `CHECK (((status)::text = ANY ((ARRAY['OPEN'::character varying, 'CLOSED'::character varying])::text[])))` |
| `ck_service_day_tickets` | CHECK | `CHECK ((((last_ticket_number >= 0) AND (last_ticket_number <= 999)) AND (occupied_count <= last_ticket_number)))` |
| `ck_service_day_tolerance` | CHECK | `CHECK (((tolerance_minutes >= 0) AND (tolerance_minutes <= 120)))` |

**Triggers**

- `trg_service_day_forbid_delete` → `tg_forbid_change()`
- `trg_service_day_updated_at` → `tg_set_updated_at()`

## site

Sedes con tópico de atención (p. ej., Javier Alzamora Valdez, Anselmo Barreto).

| Columna | Tipo | Nulo | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | integer | no | IDENTITY |  |
| `code` | character varying(10) | no |  |  |
| `name` | character varying(120) | no |  |  |
| `short_name` | character varying(40) | no |  |  |
| `ticket_prefix` | character varying(3) | no |  | Prefijo del código de turno (A → A-001). |
| `address` | character varying(250) | sí |  |  |
| `location_note` | character varying(250) | sí |  | Indicación de ubicación del tópico dentro de la sede (se usa en los correos). |
| `timezone` | character varying(50) | no | 'America/Lima'::character varying | Zona horaria IANA con la que se interpretan horarios y fechas operativas. |
| `is_active` | boolean | no | true |  |
| `created_at` | timestamp with time zone | no | now() |  |
| `updated_at` | timestamp with time zone | no | now() |  |
| `created_by` | bigint | sí |  |  |
| `updated_by` | bigint | sí |  |  |

**Restricciones**

| Nombre | Tipo | Definición |
|---|---|---|
| `site_pkey` | PK | `PRIMARY KEY (id)` |
| `uq_site_code` | UNIQUE | `UNIQUE (code)` |
| `uq_site_ticket_prefix` | UNIQUE | `UNIQUE (ticket_prefix)` |
| `site_created_by_fkey` | FK | `FOREIGN KEY (created_by) REFERENCES app_user(id)` |
| `site_updated_by_fkey` | FK | `FOREIGN KEY (updated_by) REFERENCES app_user(id)` |
| `ck_site_code_format` | CHECK | `CHECK (((code)::text ~ '^[A-Z]{2,10}$'::text))` |
| `ck_site_name_not_blank` | CHECK | `CHECK (((btrim((name)::text) <> ''::text) AND (btrim((short_name)::text) <> ''::text)))` |
| `ck_site_ticket_prefix_format` | CHECK | `CHECK (((ticket_prefix)::text ~ '^[A-Z]{1,3}$'::text))` |

**Triggers**

- `trg_site_updated_at` → `tg_set_updated_at()`

## site_closure

Días en que el tópico de una sede no atiende (feriados, cierres).

| Columna | Tipo | Nulo | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | bigint | no | IDENTITY |  |
| `site_id` | integer | no |  |  |
| `closure_date` | date | no |  |  |
| `reason` | character varying(200) | no |  |  |
| `created_at` | timestamp with time zone | no | now() |  |
| `created_by` | bigint | sí |  |  |

**Restricciones**

| Nombre | Tipo | Definición |
|---|---|---|
| `site_closure_pkey` | PK | `PRIMARY KEY (id)` |
| `uq_site_closure_site_date` | UNIQUE | `UNIQUE (site_id, closure_date)` |
| `site_closure_created_by_fkey` | FK | `FOREIGN KEY (created_by) REFERENCES app_user(id)` |
| `site_closure_site_id_fkey` | FK | `FOREIGN KEY (site_id) REFERENCES site(id)` |
| `ck_site_closure_reason_not_blank` | CHECK | `CHECK ((btrim((reason)::text) <> ''::text))` |

## site_schedule

Bloques de atención (mañana/tarde) por día de semana, con vigencia.

| Columna | Tipo | Nulo | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | bigint | no | IDENTITY |  |
| `site_id` | integer | no |  |  |
| `weekday` | smallint | no |  | Día ISO: 1 = lunes … 7 = domingo. |
| `block` | character varying(2) | no |  | AM = turno mañana, PM = turno tarde. |
| `start_time` | time without time zone | no |  |  |
| `end_time` | time without time zone | no |  |  |
| `valid_from` | date | no |  |  |
| `valid_to` | date | sí |  |  |
| `created_at` | timestamp with time zone | no | now() |  |
| `created_by` | bigint | sí |  |  |
| `updated_at` | timestamp with time zone | no | now() |  |
| `updated_by` | bigint | sí |  |  |

**Restricciones**

| Nombre | Tipo | Definición |
|---|---|---|
| `site_schedule_pkey` | PK | `PRIMARY KEY (id)` |
| `site_schedule_created_by_fkey` | FK | `FOREIGN KEY (created_by) REFERENCES app_user(id)` |
| `site_schedule_site_id_fkey` | FK | `FOREIGN KEY (site_id) REFERENCES site(id)` |
| `site_schedule_updated_by_fkey` | FK | `FOREIGN KEY (updated_by) REFERENCES app_user(id)` |
| `ex_site_schedule_block` | EXCLUDE | `EXCLUDE USING gist (site_id WITH =, weekday WITH =, block WITH =, daterange(valid_from, valid_to, '[]'::text) WITH &&)` |
| `ex_site_schedule_time_overlap` | EXCLUDE | `EXCLUDE USING gist (site_id WITH =, weekday WITH =, daterange(valid_from, valid_to, '[]'::text) WITH &&, timerange(start_time, end_time, '[)'::text) WITH &&)` |
| `ck_site_schedule_block` | CHECK | `CHECK (((block)::text = ANY ((ARRAY['AM'::character varying, 'PM'::character varying])::text[])))` |
| `ck_site_schedule_times` | CHECK | `CHECK ((end_time > start_time))` |
| `ck_site_schedule_validity` | CHECK | `CHECK (((valid_to IS NULL) OR (valid_to >= valid_from)))` |
| `ck_site_schedule_weekday` | CHECK | `CHECK (((weekday >= 1) AND (weekday <= 7)))` |

**Triggers**

- `trg_site_schedule_updated_at` → `tg_set_updated_at()`

## site_setting_version

Configuración operativa por sede, versionada por fecha de vigencia. Se aplica la versión con mayor valid_from <= fecha.

| Columna | Tipo | Nulo | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | bigint | no | IDENTITY |  |
| `site_id` | integer | no |  |  |
| `valid_from` | date | no |  |  |
| `daily_capacity` | smallint | no |  | Máximo de atenciones que ocupan cupo por día. |
| `slot_minutes` | smallint | no |  | Duración referencial de cada atención (cálculo de la hora estimada). |
| `tolerance_minutes` | smallint | no |  | Minutos desde el llamado tras los cuales puede marcarse NO_PRESENTADO. |
| `max_concurrent_in_service` | smallint | no | 1 | Atenciones simultáneas EN_ATENCION permitidas (n.º de médicos/consultorios). |
| `registration_cutoff_minutes` | smallint | no | 0 | Minutos antes del fin del último bloque en que se dejan de aceptar registros. |
| `upcoming_notice_ahead` | smallint | no | 2 | Se notifica "su atención se aproxima" cuando quedan N personas delante (0 = desactivado). |
| `allow_reregister_after_no_show` | boolean | no | false |  |
| `allow_reregister_after_cancel` | boolean | no | true |  |
| `notifications_enabled` | boolean | no | true |  |
| `change_reason` | character varying(300) | sí |  |  |
| `created_at` | timestamp with time zone | no | now() |  |
| `created_by` | bigint | sí |  |  |
| `updated_at` | timestamp with time zone | no | now() |  |
| `updated_by` | bigint | sí |  |  |

**Restricciones**

| Nombre | Tipo | Definición |
|---|---|---|
| `site_setting_version_pkey` | PK | `PRIMARY KEY (id)` |
| `uq_site_setting_version_site_from` | UNIQUE | `UNIQUE (site_id, valid_from)` |
| `site_setting_version_created_by_fkey` | FK | `FOREIGN KEY (created_by) REFERENCES app_user(id)` |
| `site_setting_version_site_id_fkey` | FK | `FOREIGN KEY (site_id) REFERENCES site(id)` |
| `site_setting_version_updated_by_fkey` | FK | `FOREIGN KEY (updated_by) REFERENCES app_user(id)` |
| `ck_site_setting_capacity` | CHECK | `CHECK (((daily_capacity >= 1) AND (daily_capacity <= 500)))` |
| `ck_site_setting_concurrent` | CHECK | `CHECK (((max_concurrent_in_service >= 1) AND (max_concurrent_in_service <= 10)))` |
| `ck_site_setting_cutoff` | CHECK | `CHECK (((registration_cutoff_minutes >= 0) AND (registration_cutoff_minutes <= 480)))` |
| `ck_site_setting_slot` | CHECK | `CHECK (((slot_minutes >= 5) AND (slot_minutes <= 120)))` |
| `ck_site_setting_tolerance` | CHECK | `CHECK (((tolerance_minutes >= 0) AND (tolerance_minutes <= 120)))` |
| `ck_site_setting_upcoming` | CHECK | `CHECK (((upcoming_notice_ahead >= 0) AND (upcoming_notice_ahead <= 20)))` |

**Triggers**

- `trg_site_setting_version_guard` → `tg_site_setting_version_guard()`

## system_parameter

Parámetros globales configurables sin modificar código.

| Columna | Tipo | Nulo | Por defecto | Descripción |
|---|---|---|---|---|
| `key` | character varying(80) | no |  |  |
| `value` | jsonb | no |  |  |
| `value_type` | character varying(10) | no |  |  |
| `description` | character varying(300) | no |  |  |
| `is_editable` | boolean | no | true |  |
| `updated_at` | timestamp with time zone | no | now() |  |
| `updated_by` | bigint | sí |  |  |

**Restricciones**

| Nombre | Tipo | Definición |
|---|---|---|
| `system_parameter_pkey` | PK | `PRIMARY KEY (key)` |
| `system_parameter_updated_by_fkey` | FK | `FOREIGN KEY (updated_by) REFERENCES app_user(id)` |
| `ck_system_parameter_key_format` | CHECK | `CHECK (((key)::text ~ '^[a-z][a-z0-9_]*(\.[a-z0-9_]+)*$'::text))` |
| `ck_system_parameter_value_type` | CHECK | `CHECK (((((value_type)::text = 'int'::text) AND (jsonb_typeof(value) = 'number'::text)) OR (((value_type)::text = 'bool'::text) AND (jsonb_typeof(value) = 'boolean'::text)) OR (((value_type)::text = 'string'::text) AND (jsonb_typeof(value) = 'string'::text)) OR (((value_type)::text = 'json'::text) AND (jsonb_typeof(value) = ANY (ARRAY['object'::text, 'array'::text])))))` |

**Triggers**

- `trg_system_parameter_updated_at` → `tg_set_updated_at()`

## user_role

Roles asignados a cada usuario.

| Columna | Tipo | Nulo | Por defecto | Descripción |
|---|---|---|---|---|
| `user_id` | bigint | no |  |  |
| `role_id` | integer | no |  |  |
| `created_at` | timestamp with time zone | no | now() |  |
| `created_by` | bigint | sí |  |  |

**Restricciones**

| Nombre | Tipo | Definición |
|---|---|---|
| `pk_user_role` | PK | `PRIMARY KEY (user_id, role_id)` |
| `user_role_created_by_fkey` | FK | `FOREIGN KEY (created_by) REFERENCES app_user(id)` |
| `user_role_role_id_fkey` | FK | `FOREIGN KEY (role_id) REFERENCES role(id)` |
| `user_role_user_id_fkey` | FK | `FOREIGN KEY (user_id) REFERENCES app_user(id)` |

**Índices adicionales**

- `ix_user_role_role`: `CREATE INDEX ix_user_role_role ON topico.user_role USING btree (role_id)`

## user_site

Alcance por sede: un usuario solo opera las sedes asignadas aquí.

| Columna | Tipo | Nulo | Por defecto | Descripción |
|---|---|---|---|---|
| `user_id` | bigint | no |  |  |
| `site_id` | integer | no |  |  |
| `created_at` | timestamp with time zone | no | now() |  |
| `created_by` | bigint | sí |  |  |

**Restricciones**

| Nombre | Tipo | Definición |
|---|---|---|
| `pk_user_site` | PK | `PRIMARY KEY (user_id, site_id)` |
| `user_site_created_by_fkey` | FK | `FOREIGN KEY (created_by) REFERENCES app_user(id)` |
| `user_site_site_id_fkey` | FK | `FOREIGN KEY (site_id) REFERENCES site(id)` |
| `user_site_user_id_fkey` | FK | `FOREIGN KEY (user_id) REFERENCES app_user(id)` |

**Índices adicionales**

- `ix_user_site_site`: `CREATE INDEX ix_user_site_site ON topico.user_site USING btree (site_id)`

## worker

Trabajadores de la CSJ Lima (dato personal). Solo datos administrativos, sin información clínica.

| Columna | Tipo | Nulo | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | bigint | no | IDENTITY |  |
| `public_id` | uuid | no | gen_random_uuid() |  |
| `document_type` | character varying(3) | no | 'DNI'::character varying |  |
| `document_number` | character varying(12) | no |  | Texto, no entero: conserva los ceros iniciales del DNI (8 dígitos). |
| `first_names` | character varying(100) | no |  |  |
| `paternal_surname` | character varying(80) | no |  |  |
| `maternal_surname` | character varying(80) | sí |  |  |
| `birth_date` | date | sí |  | Opcional. La edad se calcula a partir de esta fecha (no se guarda la edad). |
| `sex` | character(1) | sí |  |  |
| `institutional_email` | character varying(254) | sí |  |  |
| `phone` | character varying(20) | sí |  |  |
| `employee_code` | character varying(20) | sí |  |  |
| `department_id` | integer | sí |  |  |
| `work_site_id` | integer | sí |  | Sede donde labora (referencial; puede atenderse en cualquier sede). |
| `is_active` | boolean | no | true |  |
| `deactivated_at` | timestamp with time zone | sí |  |  |
| `deactivation_reason` | character varying(200) | sí |  |  |
| `source_import_id` | bigint | sí |  | Último lote de importación que creó o actualizó el registro (trazabilidad). |
| `search_name` | text | sí | GENERADA | Columna generada para búsqueda por nombre (índice trigram). |
| `created_at` | timestamp with time zone | no | now() |  |
| `updated_at` | timestamp with time zone | no | now() |  |
| `created_by` | bigint | sí |  |  |
| `updated_by` | bigint | sí |  |  |

**Restricciones**

| Nombre | Tipo | Definición |
|---|---|---|
| `worker_pkey` | PK | `PRIMARY KEY (id)` |
| `uq_worker_document` | UNIQUE | `UNIQUE (document_type, document_number)` |
| `uq_worker_employee_code` | UNIQUE | `UNIQUE (employee_code)` |
| `uq_worker_public_id` | UNIQUE | `UNIQUE (public_id)` |
| `worker_created_by_fkey` | FK | `FOREIGN KEY (created_by) REFERENCES app_user(id)` |
| `worker_department_id_fkey` | FK | `FOREIGN KEY (department_id) REFERENCES department(id)` |
| `worker_source_import_id_fkey` | FK | `FOREIGN KEY (source_import_id) REFERENCES import_batch(id)` |
| `worker_updated_by_fkey` | FK | `FOREIGN KEY (updated_by) REFERENCES app_user(id)` |
| `worker_work_site_id_fkey` | FK | `FOREIGN KEY (work_site_id) REFERENCES site(id)` |
| `ck_worker_birth_date` | CHECK | `CHECK (((birth_date IS NULL) OR (birth_date >= '1900-01-01'::date)))` |
| `ck_worker_deactivation` | CHECK | `CHECK ((is_active OR (deactivated_at IS NOT NULL)))` |
| `ck_worker_document_format` | CHECK | `CHECK (((((document_type)::text = 'DNI'::text) AND ((document_number)::text ~ '^[0-9]{8}$'::text)) OR (((document_type)::text = 'CE'::text) AND ((document_number)::text ~ '^[A-Z0-9]{8,12}$'::text)) OR (((document_type)::text = 'PAS'::text) AND ((document_number)::text ~ '^[A-Z0-9]{6,12}$'::text))))` |
| `ck_worker_document_type` | CHECK | `CHECK (((document_type)::text = ANY ((ARRAY['DNI'::character varying, 'CE'::character varying, 'PAS'::character varying])::text[])))` |
| `ck_worker_email_format` | CHECK | `CHECK (((institutional_email IS NULL) OR ((institutional_email)::text ~* '^[^@\s]+@[^@\s]+\.[^@\s]+$'::text)))` |
| `ck_worker_names_not_blank` | CHECK | `CHECK (((btrim((first_names)::text) <> ''::text) AND (btrim((paternal_surname)::text) <> ''::text)))` |
| `ck_worker_phone_format` | CHECK | `CHECK (((phone IS NULL) OR ((phone)::text ~ '^\+?[0-9 ]{6,20}$'::text)))` |
| `ck_worker_sex` | CHECK | `CHECK (((sex IS NULL) OR (sex = ANY (ARRAY['F'::bpchar, 'M'::bpchar]))))` |

**Índices adicionales**

- `ix_worker_department`: `CREATE INDEX ix_worker_department ON topico.worker USING btree (department_id)`
- `ix_worker_document_number`: `CREATE INDEX ix_worker_document_number ON topico.worker USING btree (document_number)`
- `ix_worker_search_name_trgm`: `CREATE INDEX ix_worker_search_name_trgm ON topico.worker USING gin (search_name gin_trgm_ops)`

**Triggers**

- `trg_worker_updated_at` → `tg_set_updated_at()`

## worker_coverage

Historial de habilitación EPS por trabajador. Vigente si valid_from <= fecha <= coalesce(valid_to, infinito).

| Columna | Tipo | Nulo | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | bigint | no | IDENTITY |  |
| `worker_id` | bigint | no |  |  |
| `insurer_id` | integer | no |  |  |
| `valid_from` | date | no |  |  |
| `valid_to` | date | sí |  | NULL = cobertura vigente sin fecha de término. |
| `end_reason` | character varying(200) | sí |  |  |
| `source_import_id` | bigint | sí |  |  |
| `created_at` | timestamp with time zone | no | now() |  |
| `created_by` | bigint | sí |  |  |
| `updated_at` | timestamp with time zone | no | now() |  |
| `updated_by` | bigint | sí |  |  |

**Restricciones**

| Nombre | Tipo | Definición |
|---|---|---|
| `worker_coverage_pkey` | PK | `PRIMARY KEY (id)` |
| `worker_coverage_created_by_fkey` | FK | `FOREIGN KEY (created_by) REFERENCES app_user(id)` |
| `worker_coverage_insurer_id_fkey` | FK | `FOREIGN KEY (insurer_id) REFERENCES insurer(id)` |
| `worker_coverage_source_import_id_fkey` | FK | `FOREIGN KEY (source_import_id) REFERENCES import_batch(id)` |
| `worker_coverage_updated_by_fkey` | FK | `FOREIGN KEY (updated_by) REFERENCES app_user(id)` |
| `worker_coverage_worker_id_fkey` | FK | `FOREIGN KEY (worker_id) REFERENCES worker(id)` |
| `ex_worker_coverage_overlap` | EXCLUDE | `EXCLUDE USING gist (worker_id WITH =, insurer_id WITH =, daterange(valid_from, valid_to, '[]'::text) WITH &&)` |
| `ck_worker_coverage_validity` | CHECK | `CHECK (((valid_to IS NULL) OR (valid_to >= valid_from)))` |

**Índices adicionales**

- `ix_worker_coverage_worker`: `CREATE INDEX ix_worker_coverage_worker ON topico.worker_coverage USING btree (worker_id, insurer_id, valid_from DESC)`

**Triggers**

- `trg_worker_coverage_updated_at` → `tg_set_updated_at()`
