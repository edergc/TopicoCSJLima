-- =============================================================================
--  Tópico CSJ Lima — Esquema inicial (revisión 0001)
--  PostgreSQL 16 · esquema "topico" · ejecutado por el rol topico_owner vía Alembic
--
--  Principios aplicados:
--   * Los instantes se guardan en timestamptz (UTC). Las fechas operativas se guardan en date
--     (calculadas en America/Lima por la aplicación).
--   * Nunca se elimina físicamente una atención. Los cambios de estado quedan registrados
--     y validados contra una tabla de transiciones.
--   * La capacidad y la numeración de turnos las garantiza la BD mediante triggers
--     SECURITY DEFINER más CHECK: la aplicación no puede alterar los contadores.
--   * La auditoría es de solo inserción y su cadena de hash hace detectable cualquier alteración.
--   * La aplicación (topico_app) recibe solo los privilegios estrictamente necesarios.
-- =============================================================================

SET search_path TO topico, public;

-- =============================================================================
-- 0. Tipos y funciones utilitarias
-- =============================================================================

CREATE TYPE topico.timerange AS RANGE (subtype = time);
COMMENT ON TYPE topico.timerange IS 'Rango de horas del día; se usa para impedir bloques de horario solapados.';

CREATE FUNCTION topico.tg_set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;
COMMENT ON FUNCTION topico.tg_set_updated_at() IS 'Actualiza updated_at en cada UPDATE.';

CREATE FUNCTION topico.tg_forbid_change() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'La tabla %.% es de solo inserción (% no permitido)',
        TG_TABLE_SCHEMA, TG_TABLE_NAME, TG_OP
        USING ERRCODE = 'insufficient_privilege';
END;
$$;
COMMENT ON FUNCTION topico.tg_forbid_change() IS 'Bloquea UPDATE/DELETE/TRUNCATE en tablas de solo inserción o sin borrado físico.';

-- =============================================================================
-- 1. Seguridad: usuarios, roles, permisos
-- =============================================================================

CREATE TABLE topico.app_user (
    id                     bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id              uuid         NOT NULL DEFAULT gen_random_uuid(),
    username               varchar(50)  NOT NULL,
    full_name              varchar(150) NOT NULL,
    email                  varchar(254),
    auth_provider          varchar(10)  NOT NULL DEFAULT 'LOCAL',
    password_hash          varchar(255),
    password_changed_at    timestamptz,
    must_change_password   boolean      NOT NULL DEFAULT true,
    is_active              boolean      NOT NULL DEFAULT true,
    failed_login_attempts  smallint     NOT NULL DEFAULT 0,
    locked_until           timestamptz,
    last_login_at          timestamptz,
    created_at             timestamptz  NOT NULL DEFAULT now(),
    updated_at             timestamptz  NOT NULL DEFAULT now(),
    created_by             bigint       REFERENCES topico.app_user (id),
    updated_by             bigint       REFERENCES topico.app_user (id),
    CONSTRAINT uq_app_user_public_id UNIQUE (public_id),
    CONSTRAINT uq_app_user_username UNIQUE (username),
    CONSTRAINT ck_app_user_username_format CHECK (username ~ '^[a-z0-9][a-z0-9._-]{2,49}$'),
    CONSTRAINT ck_app_user_full_name_not_blank CHECK (btrim(full_name) <> ''),
    CONSTRAINT ck_app_user_email_format CHECK (email IS NULL OR email ~* '^[^@\s]+@[^@\s]+\.[^@\s]+$'),
    CONSTRAINT ck_app_user_auth_provider CHECK (auth_provider IN ('LOCAL', 'LDAP')),
    CONSTRAINT ck_app_user_local_password CHECK (auth_provider <> 'LOCAL' OR password_hash IS NOT NULL),
    CONSTRAINT ck_app_user_failed_attempts CHECK (failed_login_attempts >= 0)
);
COMMENT ON TABLE  topico.app_user IS 'Usuarios del sistema (personal administrativo). No incluye a los trabajadores atendidos.';
COMMENT ON COLUMN topico.app_user.public_id IS 'Identificador expuesto por la API (no enumerable).';
COMMENT ON COLUMN topico.app_user.username IS 'Nombre de usuario en minúsculas. En Fase 3 coincidirá con la cuenta AD/LDAP.';
COMMENT ON COLUMN topico.app_user.auth_provider IS 'LOCAL: contraseña propia (hash Argon2id). LDAP: autenticación institucional (Fase 3).';
COMMENT ON COLUMN topico.app_user.password_hash IS 'Hash Argon2id. Nunca texto plano. NULL solo para LDAP.';
COMMENT ON COLUMN topico.app_user.locked_until IS 'Bloqueo temporal por intentos fallidos consecutivos.';

CREATE TABLE topico.role (
    id           integer      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code         varchar(30)  NOT NULL,
    name         varchar(80)  NOT NULL,
    description  varchar(300),
    is_system    boolean      NOT NULL DEFAULT false,
    is_active    boolean      NOT NULL DEFAULT true,
    created_at   timestamptz  NOT NULL DEFAULT now(),
    updated_at   timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT uq_role_code UNIQUE (code),
    CONSTRAINT ck_role_code_format CHECK (code ~ '^[A-Z][A-Z0-9_]{1,29}$')
);
COMMENT ON TABLE  topico.role IS 'Roles: agrupaciones de permisos. is_system = rol base que no puede eliminarse.';

CREATE TABLE topico.permission (
    id           integer      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code         varchar(60)  NOT NULL,
    module       varchar(30)  NOT NULL,
    description  varchar(300) NOT NULL,
    CONSTRAINT uq_permission_code UNIQUE (code),
    CONSTRAINT ck_permission_code_format CHECK (code ~ '^[a-z_]+:[a-z_]+$')
);
COMMENT ON TABLE  topico.permission IS 'Permisos atómicos (recurso:acción). Los define el código; la app solo los lee.';

CREATE TABLE topico.role_permission (
    role_id        integer     NOT NULL REFERENCES topico.role (id),
    permission_id  integer     NOT NULL REFERENCES topico.permission (id),
    created_at     timestamptz NOT NULL DEFAULT now(),
    created_by     bigint      REFERENCES topico.app_user (id),
    CONSTRAINT pk_role_permission PRIMARY KEY (role_id, permission_id)
);
CREATE INDEX ix_role_permission_permission ON topico.role_permission (permission_id);
COMMENT ON TABLE topico.role_permission IS 'Asignación de permisos a roles.';

CREATE TABLE topico.user_role (
    user_id     bigint      NOT NULL REFERENCES topico.app_user (id),
    role_id     integer     NOT NULL REFERENCES topico.role (id),
    created_at  timestamptz NOT NULL DEFAULT now(),
    created_by  bigint      REFERENCES topico.app_user (id),
    CONSTRAINT pk_user_role PRIMARY KEY (user_id, role_id)
);
CREATE INDEX ix_user_role_role ON topico.user_role (role_id);
COMMENT ON TABLE topico.user_role IS 'Roles asignados a cada usuario.';

-- =============================================================================
-- 2. Sedes
-- =============================================================================

CREATE TABLE topico.site (
    id             integer      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code           varchar(10)  NOT NULL,
    name           varchar(120) NOT NULL,
    short_name     varchar(40)  NOT NULL,
    ticket_prefix  varchar(3)   NOT NULL,
    address        varchar(250),
    location_note  varchar(250),
    timezone       varchar(50)  NOT NULL DEFAULT 'America/Lima',
    is_active      boolean      NOT NULL DEFAULT true,
    created_at     timestamptz  NOT NULL DEFAULT now(),
    updated_at     timestamptz  NOT NULL DEFAULT now(),
    created_by     bigint       REFERENCES topico.app_user (id),
    updated_by     bigint       REFERENCES topico.app_user (id),
    CONSTRAINT uq_site_code UNIQUE (code),
    CONSTRAINT uq_site_ticket_prefix UNIQUE (ticket_prefix),
    CONSTRAINT ck_site_code_format CHECK (code ~ '^[A-Z]{2,10}$'),
    CONSTRAINT ck_site_ticket_prefix_format CHECK (ticket_prefix ~ '^[A-Z]{1,3}$'),
    CONSTRAINT ck_site_name_not_blank CHECK (btrim(name) <> '' AND btrim(short_name) <> '')
);
COMMENT ON TABLE  topico.site IS 'Sedes con tópico de atención (p. ej., Javier Alzamora Valdez, Anselmo Barreto).';
COMMENT ON COLUMN topico.site.ticket_prefix IS 'Prefijo del código de turno (A → A-001).';
COMMENT ON COLUMN topico.site.location_note IS 'Indicación de ubicación del tópico dentro de la sede (se usa en los correos).';
COMMENT ON COLUMN topico.site.timezone IS 'Zona horaria IANA con la que se interpretan horarios y fechas operativas.';

CREATE TABLE topico.user_site (
    user_id     bigint      NOT NULL REFERENCES topico.app_user (id),
    site_id     integer     NOT NULL REFERENCES topico.site (id),
    created_at  timestamptz NOT NULL DEFAULT now(),
    created_by  bigint      REFERENCES topico.app_user (id),
    CONSTRAINT pk_user_site PRIMARY KEY (user_id, site_id)
);
CREATE INDEX ix_user_site_site ON topico.user_site (site_id);
COMMENT ON TABLE topico.user_site IS 'Alcance por sede: un usuario solo opera las sedes asignadas aquí.';

CREATE TABLE topico.refresh_token (
    id              bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id         bigint       NOT NULL REFERENCES topico.app_user (id),
    family_id       uuid         NOT NULL,
    token_hash      char(64)     NOT NULL,
    issued_at       timestamptz  NOT NULL DEFAULT now(),
    expires_at      timestamptz  NOT NULL,
    revoked_at      timestamptz,
    revoked_reason  varchar(30),
    replaced_by_id  bigint       REFERENCES topico.refresh_token (id),
    ip              inet,
    user_agent      varchar(500),
    CONSTRAINT uq_refresh_token_hash UNIQUE (token_hash),
    CONSTRAINT ck_refresh_token_expiry CHECK (expires_at > issued_at),
    CONSTRAINT ck_refresh_token_hash_format CHECK (token_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_refresh_token_revoked_reason CHECK (
        revoked_reason IS NULL OR revoked_reason IN ('ROTATED', 'LOGOUT', 'REUSE_DETECTED', 'ADMIN', 'PASSWORD_CHANGED'))
);
CREATE INDEX ix_refresh_token_user ON topico.refresh_token (user_id);
CREATE INDEX ix_refresh_token_family ON topico.refresh_token (family_id);
COMMENT ON TABLE  topico.refresh_token IS 'Sesiones (refresh tokens rotativos). Solo se guarda el SHA-256 del token.';
COMMENT ON COLUMN topico.refresh_token.family_id IS 'Cadena de rotación. Si se reutiliza un token ya rotado, se revoca toda la familia.';

-- =============================================================================
-- 3. Configuración
-- =============================================================================

CREATE TABLE topico.system_parameter (
    key          varchar(80)  PRIMARY KEY,
    value        jsonb        NOT NULL,
    value_type   varchar(10)  NOT NULL,
    description  varchar(300) NOT NULL,
    is_editable  boolean      NOT NULL DEFAULT true,
    updated_at   timestamptz  NOT NULL DEFAULT now(),
    updated_by   bigint       REFERENCES topico.app_user (id),
    CONSTRAINT ck_system_parameter_key_format CHECK (key ~ '^[a-z][a-z0-9_]*(\.[a-z0-9_]+)*$'),
    CONSTRAINT ck_system_parameter_value_type CHECK (
           (value_type = 'int'    AND jsonb_typeof(value) = 'number')
        OR (value_type = 'bool'   AND jsonb_typeof(value) = 'boolean')
        OR (value_type = 'string' AND jsonb_typeof(value) = 'string')
        OR (value_type = 'json'   AND jsonb_typeof(value) IN ('object', 'array')))
);
COMMENT ON TABLE topico.system_parameter IS 'Parámetros globales configurables sin modificar código.';

CREATE TABLE topico.site_setting_version (
    id                              bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    site_id                         integer      NOT NULL REFERENCES topico.site (id),
    valid_from                      date         NOT NULL,
    daily_capacity                  smallint     NOT NULL,
    slot_minutes                    smallint     NOT NULL,
    tolerance_minutes               smallint     NOT NULL,
    max_concurrent_in_service       smallint     NOT NULL DEFAULT 1,
    registration_cutoff_minutes     smallint     NOT NULL DEFAULT 0,
    upcoming_notice_ahead           smallint     NOT NULL DEFAULT 2,
    allow_reregister_after_no_show  boolean      NOT NULL DEFAULT false,
    allow_reregister_after_cancel   boolean      NOT NULL DEFAULT true,
    notifications_enabled           boolean      NOT NULL DEFAULT true,
    change_reason                   varchar(300),
    created_at                      timestamptz  NOT NULL DEFAULT now(),
    created_by                      bigint       REFERENCES topico.app_user (id),
    updated_at                      timestamptz  NOT NULL DEFAULT now(),
    updated_by                      bigint       REFERENCES topico.app_user (id),
    CONSTRAINT uq_site_setting_version_site_from UNIQUE (site_id, valid_from),
    CONSTRAINT ck_site_setting_capacity CHECK (daily_capacity BETWEEN 1 AND 500),
    CONSTRAINT ck_site_setting_slot CHECK (slot_minutes BETWEEN 5 AND 120),
    CONSTRAINT ck_site_setting_tolerance CHECK (tolerance_minutes BETWEEN 0 AND 120),
    CONSTRAINT ck_site_setting_concurrent CHECK (max_concurrent_in_service BETWEEN 1 AND 10),
    CONSTRAINT ck_site_setting_cutoff CHECK (registration_cutoff_minutes BETWEEN 0 AND 480),
    CONSTRAINT ck_site_setting_upcoming CHECK (upcoming_notice_ahead BETWEEN 0 AND 20)
);
COMMENT ON TABLE  topico.site_setting_version IS 'Configuración operativa por sede, versionada por fecha de vigencia. Se aplica la versión con mayor valid_from <= fecha.';
COMMENT ON COLUMN topico.site_setting_version.daily_capacity IS 'Máximo de atenciones que ocupan cupo por día.';
COMMENT ON COLUMN topico.site_setting_version.slot_minutes IS 'Duración referencial de cada atención (cálculo de la hora estimada).';
COMMENT ON COLUMN topico.site_setting_version.tolerance_minutes IS 'Minutos desde el llamado tras los cuales puede marcarse NO_PRESENTADO.';
COMMENT ON COLUMN topico.site_setting_version.max_concurrent_in_service IS 'Atenciones simultáneas EN_ATENCION permitidas (n.º de médicos/consultorios).';
COMMENT ON COLUMN topico.site_setting_version.registration_cutoff_minutes IS 'Minutos antes del fin del último bloque en que se dejan de aceptar registros.';
COMMENT ON COLUMN topico.site_setting_version.upcoming_notice_ahead IS 'Se notifica "su atención se aproxima" cuando quedan N personas delante (0 = desactivado).';

CREATE TABLE topico.site_schedule (
    id           bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    site_id      integer      NOT NULL REFERENCES topico.site (id),
    weekday      smallint     NOT NULL,
    block        varchar(2)   NOT NULL,
    start_time   time         NOT NULL,
    end_time     time         NOT NULL,
    valid_from   date         NOT NULL,
    valid_to     date,
    created_at   timestamptz  NOT NULL DEFAULT now(),
    created_by   bigint       REFERENCES topico.app_user (id),
    updated_at   timestamptz  NOT NULL DEFAULT now(),
    updated_by   bigint       REFERENCES topico.app_user (id),
    CONSTRAINT ck_site_schedule_weekday CHECK (weekday BETWEEN 1 AND 7),
    CONSTRAINT ck_site_schedule_block CHECK (block IN ('AM', 'PM')),
    CONSTRAINT ck_site_schedule_times CHECK (end_time > start_time),
    CONSTRAINT ck_site_schedule_validity CHECK (valid_to IS NULL OR valid_to >= valid_from),
    -- Un mismo bloque no puede definirse dos veces en periodos que se superponen...
    CONSTRAINT ex_site_schedule_block EXCLUDE USING gist (
        site_id WITH =, weekday WITH =, block WITH =,
        daterange(valid_from, valid_to, '[]') WITH &&),
    -- ...y dos bloques del mismo día no pueden solaparse en horas.
    CONSTRAINT ex_site_schedule_time_overlap EXCLUDE USING gist (
        site_id WITH =, weekday WITH =,
        daterange(valid_from, valid_to, '[]') WITH &&,
        topico.timerange(start_time, end_time, '[)') WITH &&)
);
COMMENT ON TABLE  topico.site_schedule IS 'Bloques de atención (mañana/tarde) por día de semana, con vigencia.';
COMMENT ON COLUMN topico.site_schedule.weekday IS 'Día ISO: 1 = lunes … 7 = domingo.';
COMMENT ON COLUMN topico.site_schedule.block IS 'AM = turno mañana, PM = turno tarde.';

CREATE TABLE topico.site_closure (
    id            bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    site_id       integer      NOT NULL REFERENCES topico.site (id),
    closure_date  date         NOT NULL,
    reason        varchar(200) NOT NULL,
    created_at    timestamptz  NOT NULL DEFAULT now(),
    created_by    bigint       REFERENCES topico.app_user (id),
    CONSTRAINT uq_site_closure_site_date UNIQUE (site_id, closure_date),
    CONSTRAINT ck_site_closure_reason_not_blank CHECK (btrim(reason) <> '')
);
COMMENT ON TABLE topico.site_closure IS 'Días en que el tópico de una sede no atiende (feriados, cierres).';

-- =============================================================================
-- 4. Importaciones (staging)
-- =============================================================================

CREATE TABLE topico.import_batch (
    id                 bigint        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id          uuid          NOT NULL DEFAULT gen_random_uuid(),
    kind               varchar(30)   NOT NULL,
    status             varchar(12)   NOT NULL DEFAULT 'UPLOADED',
    file_name          varchar(255)  NOT NULL,
    file_sha256        char(64)      NOT NULL,
    file_size_bytes    integer       NOT NULL,
    sheet_name         varchar(100),
    options            jsonb         NOT NULL DEFAULT '{}'::jsonb,
    column_mapping     jsonb,
    total_rows         integer       NOT NULL DEFAULT 0,
    new_count          integer       NOT NULL DEFAULT 0,
    update_count       integer       NOT NULL DEFAULT 0,
    unchanged_count    integer       NOT NULL DEFAULT 0,
    error_count        integer       NOT NULL DEFAULT 0,
    duplicate_count    integer       NOT NULL DEFAULT 0,
    deactivated_count  integer       NOT NULL DEFAULT 0,
    failure_message    varchar(1000),
    created_at         timestamptz   NOT NULL DEFAULT now(),
    created_by         bigint        NOT NULL REFERENCES topico.app_user (id),
    validated_at       timestamptz,
    confirmed_at       timestamptz,
    confirmed_by       bigint        REFERENCES topico.app_user (id),
    discarded_at       timestamptz,
    discarded_by       bigint        REFERENCES topico.app_user (id),
    updated_at         timestamptz   NOT NULL DEFAULT now(),
    CONSTRAINT uq_import_batch_public_id UNIQUE (public_id),
    CONSTRAINT ck_import_batch_kind CHECK (kind IN ('WORKERS_EPS', 'HISTORICAL_APPOINTMENTS')),
    CONSTRAINT ck_import_batch_status CHECK (status IN ('UPLOADED', 'VALIDATED', 'CONFIRMED', 'DISCARDED', 'FAILED')),
    CONSTRAINT ck_import_batch_sha256 CHECK (file_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_import_batch_size CHECK (file_size_bytes > 0),
    CONSTRAINT ck_import_batch_counts CHECK (
        total_rows >= 0 AND new_count >= 0 AND update_count >= 0 AND unchanged_count >= 0
        AND error_count >= 0 AND duplicate_count >= 0 AND deactivated_count >= 0),
    CONSTRAINT ck_import_batch_confirmed CHECK (
        status <> 'CONFIRMED' OR (confirmed_at IS NOT NULL AND confirmed_by IS NOT NULL)),
    CONSTRAINT ck_import_batch_discarded CHECK (
        status <> 'DISCARDED' OR (discarded_at IS NOT NULL AND discarded_by IS NOT NULL))
);
-- Un mismo archivo no puede confirmarse dos veces para el mismo tipo de importación.
CREATE UNIQUE INDEX uq_import_batch_confirmed_file
    ON topico.import_batch (kind, file_sha256) WHERE status = 'CONFIRMED';
CREATE INDEX ix_import_batch_created ON topico.import_batch (created_at DESC);
COMMENT ON TABLE  topico.import_batch IS 'Lote de importación de Excel. Flujo: UPLOADED → VALIDATED → CONFIRMED | DISCARDED | FAILED.';
COMMENT ON COLUMN topico.import_batch.file_sha256 IS 'Huella del archivo; evita reimportar el mismo contenido.';
COMMENT ON COLUMN topico.import_batch.options IS 'Opciones elegidas al confirmar (p. ej., dar de baja la cobertura de los ausentes).';

-- =============================================================================
-- 5. Trabajadores y cobertura EPS
-- =============================================================================

CREATE TABLE topico.department (
    id               integer      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code             varchar(30),
    name             varchar(200) NOT NULL,
    normalized_name  varchar(200) NOT NULL,
    is_active        boolean      NOT NULL DEFAULT true,
    created_at       timestamptz  NOT NULL DEFAULT now(),
    updated_at       timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT uq_department_code UNIQUE (code),
    CONSTRAINT uq_department_normalized_name UNIQUE (normalized_name),
    CONSTRAINT ck_department_name_not_blank CHECK (btrim(name) <> '')
);
COMMENT ON TABLE  topico.department IS 'Dependencias (órganos jurisdiccionales/administrativos) de la CSJ Lima.';
COMMENT ON COLUMN topico.department.normalized_name IS 'Nombre en mayúsculas, sin tildes ni espacios repetidos; evita duplicados al importar.';

CREATE TABLE topico.insurer (
    id          integer      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code        varchar(20)  NOT NULL,
    name        varchar(120) NOT NULL,
    is_active   boolean      NOT NULL DEFAULT true,
    created_at  timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT uq_insurer_code UNIQUE (code),
    CONSTRAINT ck_insurer_code_format CHECK (code ~ '^[A-Z][A-Z0-9_]{1,19}$')
);
COMMENT ON TABLE topico.insurer IS 'Entidades prestadoras de salud (EPS). Inicialmente: RIMAC.';

CREATE TABLE topico.worker (
    id                   bigint        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id            uuid          NOT NULL DEFAULT gen_random_uuid(),
    document_type        varchar(3)    NOT NULL DEFAULT 'DNI',
    document_number      varchar(12)   NOT NULL,
    first_names          varchar(100)  NOT NULL,
    paternal_surname     varchar(80)   NOT NULL,
    maternal_surname     varchar(80),
    birth_date           date,
    sex                  char(1),
    institutional_email  varchar(254),
    phone                varchar(20),
    employee_code        varchar(20),
    department_id        integer       REFERENCES topico.department (id),
    work_site_id         integer       REFERENCES topico.site (id),
    is_active            boolean       NOT NULL DEFAULT true,
    deactivated_at       timestamptz,
    deactivation_reason  varchar(200),
    source_import_id     bigint        REFERENCES topico.import_batch (id),
    search_name          text          GENERATED ALWAYS AS (
                            upper(paternal_surname || ' ' || coalesce(maternal_surname, '') || ' ' || first_names)
                         ) STORED,
    created_at           timestamptz   NOT NULL DEFAULT now(),
    updated_at           timestamptz   NOT NULL DEFAULT now(),
    created_by           bigint        REFERENCES topico.app_user (id),
    updated_by           bigint        REFERENCES topico.app_user (id),
    CONSTRAINT uq_worker_public_id UNIQUE (public_id),
    CONSTRAINT uq_worker_document UNIQUE (document_type, document_number),
    CONSTRAINT uq_worker_employee_code UNIQUE (employee_code),
    CONSTRAINT ck_worker_document_type CHECK (document_type IN ('DNI', 'CE', 'PAS')),
    CONSTRAINT ck_worker_document_format CHECK (
           (document_type = 'DNI' AND document_number ~ '^[0-9]{8}$')
        OR (document_type = 'CE'  AND document_number ~ '^[A-Z0-9]{8,12}$')
        OR (document_type = 'PAS' AND document_number ~ '^[A-Z0-9]{6,12}$')),
    CONSTRAINT ck_worker_names_not_blank CHECK (btrim(first_names) <> '' AND btrim(paternal_surname) <> ''),
    CONSTRAINT ck_worker_sex CHECK (sex IS NULL OR sex IN ('F', 'M')),
    CONSTRAINT ck_worker_birth_date CHECK (birth_date IS NULL OR birth_date >= DATE '1900-01-01'),
    CONSTRAINT ck_worker_email_format CHECK (
        institutional_email IS NULL OR institutional_email ~* '^[^@\s]+@[^@\s]+\.[^@\s]+$'),
    CONSTRAINT ck_worker_phone_format CHECK (phone IS NULL OR phone ~ '^\+?[0-9 ]{6,20}$'),
    CONSTRAINT ck_worker_deactivation CHECK (is_active OR deactivated_at IS NOT NULL)
);
CREATE INDEX ix_worker_document_number ON topico.worker (document_number);
CREATE INDEX ix_worker_department ON topico.worker (department_id);
CREATE INDEX ix_worker_search_name_trgm ON topico.worker USING gin (search_name gin_trgm_ops);
COMMENT ON TABLE  topico.worker IS 'Trabajadores de la CSJ Lima (dato personal). Solo datos administrativos, sin información clínica.';
COMMENT ON COLUMN topico.worker.document_number IS 'Texto, no entero: conserva los ceros iniciales del DNI (8 dígitos).';
COMMENT ON COLUMN topico.worker.birth_date IS 'Opcional. La edad se calcula a partir de esta fecha (no se guarda la edad).';
COMMENT ON COLUMN topico.worker.work_site_id IS 'Sede donde labora (referencial; puede atenderse en cualquier sede).';
COMMENT ON COLUMN topico.worker.search_name IS 'Columna generada para búsqueda por nombre (índice trigram).';
COMMENT ON COLUMN topico.worker.source_import_id IS 'Último lote de importación que creó o actualizó el registro (trazabilidad).';

CREATE TABLE topico.worker_coverage (
    id                bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    worker_id         bigint       NOT NULL REFERENCES topico.worker (id),
    insurer_id        integer      NOT NULL REFERENCES topico.insurer (id),
    valid_from        date         NOT NULL,
    valid_to          date,
    end_reason        varchar(200),
    source_import_id  bigint       REFERENCES topico.import_batch (id),
    created_at        timestamptz  NOT NULL DEFAULT now(),
    created_by        bigint       REFERENCES topico.app_user (id),
    updated_at        timestamptz  NOT NULL DEFAULT now(),
    updated_by        bigint       REFERENCES topico.app_user (id),
    CONSTRAINT ck_worker_coverage_validity CHECK (valid_to IS NULL OR valid_to >= valid_from),
    CONSTRAINT ex_worker_coverage_overlap EXCLUDE USING gist (
        worker_id WITH =, insurer_id WITH =, daterange(valid_from, valid_to, '[]') WITH &&)
);
CREATE INDEX ix_worker_coverage_worker ON topico.worker_coverage (worker_id, insurer_id, valid_from DESC);
COMMENT ON TABLE  topico.worker_coverage IS 'Historial de habilitación EPS por trabajador. Vigente si valid_from <= fecha <= coalesce(valid_to, infinito).';
COMMENT ON COLUMN topico.worker_coverage.valid_to IS 'NULL = cobertura vigente sin fecha de término.';

CREATE TABLE topico.import_row (
    id                bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    batch_id          bigint       NOT NULL REFERENCES topico.import_batch (id),
    row_number        integer      NOT NULL,
    raw               jsonb        NOT NULL,
    normalized        jsonb,
    outcome           varchar(20)  NOT NULL,
    errors            jsonb        NOT NULL DEFAULT '[]'::jsonb,
    warnings          jsonb        NOT NULL DEFAULT '[]'::jsonb,
    changes           jsonb,
    target_worker_id  bigint       REFERENCES topico.worker (id),
    created_at        timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT uq_import_row_batch_row UNIQUE (batch_id, row_number),
    CONSTRAINT ck_import_row_number CHECK (row_number > 0),
    CONSTRAINT ck_import_row_outcome CHECK (
        outcome IN ('NEW', 'UPDATE', 'UNCHANGED', 'ERROR', 'DUPLICATE_IN_FILE')),
    CONSTRAINT ck_import_row_errors_array CHECK (
        jsonb_typeof(errors) = 'array' AND jsonb_typeof(warnings) = 'array'),
    CONSTRAINT ck_import_row_error_has_messages CHECK (outcome <> 'ERROR' OR jsonb_array_length(errors) > 0)
);
CREATE INDEX ix_import_row_batch_outcome ON topico.import_row (batch_id, outcome);
COMMENT ON TABLE  topico.import_row IS 'Filas en staging de un lote: dato crudo, dato normalizado, resultado de validación y diferencias.';
COMMENT ON COLUMN topico.import_row.row_number IS 'Número de fila en la hoja de Excel (para que el usuario ubique el error).';
COMMENT ON COLUMN topico.import_row.changes IS 'Diferencias campo a campo {campo: [anterior, nuevo]} cuando outcome = UPDATE.';

-- =============================================================================
-- 6. Catálogos de la atención
-- =============================================================================

CREATE TABLE topico.reason (
    id             integer      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    type           varchar(15)  NOT NULL,
    code           varchar(40)  NOT NULL,
    label          varchar(150) NOT NULL,
    requires_note  boolean      NOT NULL DEFAULT false,
    is_active      boolean      NOT NULL DEFAULT true,
    sort_order     smallint     NOT NULL DEFAULT 0,
    created_at     timestamptz  NOT NULL DEFAULT now(),
    updated_at     timestamptz  NOT NULL DEFAULT now(),
    updated_by     bigint       REFERENCES topico.app_user (id),
    CONSTRAINT uq_reason_type_code UNIQUE (type, code),
    CONSTRAINT ck_reason_type CHECK (type IN ('CANCEL', 'VOID', 'NO_SHOW', 'REQUEUE')),
    CONSTRAINT ck_reason_code_format CHECK (code ~ '^[A-Z][A-Z0-9_]{1,39}$')
);
COMMENT ON TABLE  topico.reason IS 'Motivos administrativos (cancelación, anulación, no presentado, devolución a cola). Nunca motivos clínicos.';
COMMENT ON COLUMN topico.reason.requires_note IS 'Si es true, la acción exige una observación (p. ej., motivo "Otro").';

CREATE TABLE topico.appointment_status (
    code               varchar(15)  PRIMARY KEY,
    label              varchar(40)  NOT NULL,
    description        varchar(200) NOT NULL,
    consumes_capacity  boolean      NOT NULL,
    is_final           boolean      NOT NULL,
    is_active_queue    boolean      NOT NULL,
    sort_order         smallint     NOT NULL,
    CONSTRAINT ck_appointment_status_final CHECK (NOT (is_final AND is_active_queue))
);
COMMENT ON TABLE  topico.appointment_status IS 'Estados de la atención. Define qué estados ocupan cupo y cuáles son finales.';
COMMENT ON COLUMN topico.appointment_status.consumes_capacity IS 'true: la atención ocupa un cupo del día en este estado.';
COMMENT ON COLUMN topico.appointment_status.is_active_queue IS 'true: la atención está viva (cuenta para la regla "una atención activa por trabajador y día").';

CREATE TABLE topico.appointment_status_transition (
    from_status  varchar(15)  NOT NULL REFERENCES topico.appointment_status (code),
    to_status    varchar(15)  NOT NULL REFERENCES topico.appointment_status (code),
    action       varchar(20)  NOT NULL,
    CONSTRAINT pk_appointment_status_transition PRIMARY KEY (from_status, to_status),
    CONSTRAINT ck_appointment_status_transition_distinct CHECK (from_status <> to_status)
);
COMMENT ON TABLE topico.appointment_status_transition IS 'Máquina de estados: únicas transiciones permitidas. La BD rechaza cualquier otra.';

-- =============================================================================
-- 7. Agenda diaria y atenciones
-- =============================================================================

CREATE TABLE topico.service_day (
    id                         bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    site_id                    integer      NOT NULL REFERENCES topico.site (id),
    service_date               date         NOT NULL,
    setting_version_id         bigint       NOT NULL REFERENCES topico.site_setting_version (id),
    status                     varchar(6)   NOT NULL DEFAULT 'OPEN',
    capacity                   smallint     NOT NULL,
    slot_minutes               smallint     NOT NULL,
    tolerance_minutes          smallint     NOT NULL,
    max_concurrent_in_service  smallint     NOT NULL,
    occupied_count             smallint     NOT NULL DEFAULT 0,
    last_ticket_number         smallint     NOT NULL DEFAULT 0,
    opened_at                  timestamptz  NOT NULL DEFAULT now(),
    closed_at                  timestamptz,
    closed_by                  bigint       REFERENCES topico.app_user (id),
    capacity_adjusted_at       timestamptz,
    capacity_adjusted_by       bigint       REFERENCES topico.app_user (id),
    capacity_adjust_reason     varchar(300),
    created_at                 timestamptz  NOT NULL DEFAULT now(),
    updated_at                 timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT uq_service_day_site_date UNIQUE (site_id, service_date),
    CONSTRAINT ck_service_day_status CHECK (status IN ('OPEN', 'CLOSED')),
    CONSTRAINT ck_service_day_capacity CHECK (occupied_count >= 0 AND occupied_count <= capacity),
    CONSTRAINT ck_service_day_capacity_range CHECK (capacity BETWEEN 0 AND 500),
    CONSTRAINT ck_service_day_tickets CHECK (last_ticket_number BETWEEN 0 AND 999 AND occupied_count <= last_ticket_number),
    CONSTRAINT ck_service_day_slot CHECK (slot_minutes BETWEEN 5 AND 120),
    CONSTRAINT ck_service_day_tolerance CHECK (tolerance_minutes BETWEEN 0 AND 120),
    CONSTRAINT ck_service_day_concurrent CHECK (max_concurrent_in_service BETWEEN 1 AND 10),
    CONSTRAINT ck_service_day_closed CHECK (status <> 'CLOSED' OR closed_at IS NOT NULL),
    CONSTRAINT ck_service_day_adjust CHECK (
        capacity_adjusted_at IS NULL OR (capacity_adjusted_by IS NOT NULL AND capacity_adjust_reason IS NOT NULL))
);
COMMENT ON TABLE  topico.service_day IS 'Día operativo por sede. Congela la configuración vigente y es el punto de serialización de registros (bloqueo de fila).';
COMMENT ON COLUMN topico.service_day.capacity IS 'Capacidad congelada al abrir el día; solo cambia por ajuste explícito y auditado.';
COMMENT ON COLUMN topico.service_day.occupied_count IS 'Cupos ocupados. Lo mantienen los triggers de appointment; la aplicación no puede escribirlo.';
COMMENT ON COLUMN topico.service_day.last_ticket_number IS 'Último número de turno emitido (correlativo sin reutilización). Lo mantiene un trigger.';

CREATE TABLE topico.appointment (
    id                     bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id              uuid         NOT NULL DEFAULT gen_random_uuid(),
    service_day_id         bigint       NOT NULL REFERENCES topico.service_day (id),
    site_id                integer      NOT NULL REFERENCES topico.site (id),
    service_date           date         NOT NULL,
    worker_id              bigint       NOT NULL REFERENCES topico.worker (id),
    ticket_number          smallint     NOT NULL,
    ticket_code            varchar(8)   NOT NULL,
    status                 varchar(15)  NOT NULL REFERENCES topico.appointment_status (code),
    channel                varchar(10)  NOT NULL,
    origin_appointment_id  bigint       REFERENCES topico.appointment (id),
    admin_note             varchar(300),
    registered_at          timestamptz  NOT NULL DEFAULT now(),
    registered_by          bigint       NOT NULL REFERENCES topico.app_user (id),
    queued_at              timestamptz,
    called_at              timestamptz,
    called_by              bigint       REFERENCES topico.app_user (id),
    call_count             smallint     NOT NULL DEFAULT 0,
    started_at             timestamptz,
    started_by             bigint       REFERENCES topico.app_user (id),
    finished_at            timestamptz,
    finished_by            bigint       REFERENCES topico.app_user (id),
    closed_at              timestamptz,
    closed_by              bigint       REFERENCES topico.app_user (id),
    close_reason_id        integer      REFERENCES topico.reason (id),
    close_note             varchar(300),
    version                integer      NOT NULL DEFAULT 1,
    created_at             timestamptz  NOT NULL DEFAULT now(),
    updated_at             timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT uq_appointment_public_id UNIQUE (public_id),
    CONSTRAINT uq_appointment_day_ticket UNIQUE (service_day_id, ticket_number),
    CONSTRAINT ck_appointment_channel CHECK (channel IN ('PHONE', 'WALK_IN', 'WEB', 'MIGRATION')),
    CONSTRAINT ck_appointment_ticket CHECK (ticket_number > 0 AND ticket_code ~ '^[A-Z]{1,3}-[0-9]{3}$'),
    CONSTRAINT ck_appointment_call_count CHECK (call_count >= 0),
    CONSTRAINT ck_appointment_version CHECK (version > 0),
    CONSTRAINT ck_appointment_not_self_origin CHECK (origin_appointment_id IS NULL OR origin_appointment_id <> id),
    -- Coherencia entre el estado y las marcas de tiempo
    CONSTRAINT ck_appointment_called_data CHECK (
        status NOT IN ('LLAMADO', 'NO_PRESENTADO') OR channel = 'MIGRATION'
        OR (called_at IS NOT NULL AND called_by IS NOT NULL)),
    CONSTRAINT ck_appointment_started_data CHECK (
        status NOT IN ('EN_ATENCION', 'ATENDIDO') OR channel = 'MIGRATION'
        OR (started_at IS NOT NULL AND started_by IS NOT NULL)),
    CONSTRAINT ck_appointment_finished_data CHECK (
        status <> 'ATENDIDO' OR channel = 'MIGRATION' OR (finished_at IS NOT NULL AND finished_by IS NOT NULL)),
    CONSTRAINT ck_appointment_closed_data CHECK (
        status NOT IN ('CANCELADO', 'NO_PRESENTADO', 'ANULADO')
        OR (closed_at IS NOT NULL AND closed_by IS NOT NULL
            AND (close_reason_id IS NOT NULL OR channel = 'MIGRATION'))),
    CONSTRAINT ck_appointment_time_order CHECK (
            (called_at   IS NULL OR called_at   >= registered_at)
        AND (started_at  IS NULL OR started_at  >= registered_at)
        AND (finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at)
        AND (closed_at   IS NULL OR closed_at   >= registered_at))
);
-- Regla RN-17: un trabajador no puede tener dos atenciones vivas el mismo día (en ninguna sede).
CREATE UNIQUE INDEX uq_appointment_worker_active_day ON topico.appointment (worker_id, service_date)
    WHERE status IN ('REGISTRADO', 'EN_ESPERA', 'LLAMADO', 'EN_ATENCION');
CREATE INDEX ix_appointment_queue ON topico.appointment (service_day_id, status, ticket_number);
CREATE INDEX ix_appointment_site_date ON topico.appointment (site_id, service_date);
CREATE INDEX ix_appointment_worker_date ON topico.appointment (worker_id, service_date DESC);
CREATE INDEX ix_appointment_origin ON topico.appointment (origin_appointment_id) WHERE origin_appointment_id IS NOT NULL;
CREATE INDEX ix_appointment_close_reason ON topico.appointment (close_reason_id) WHERE close_reason_id IS NOT NULL;
COMMENT ON TABLE  topico.appointment IS 'Solicitud de atención con turno. Registro administrativo: NO contiene información clínica. Nunca se elimina.';
COMMENT ON COLUMN topico.appointment.site_id IS 'Desnormalizado desde service_day (lo asigna el trigger) para índices y reportes.';
COMMENT ON COLUMN topico.appointment.service_date IS 'Fecha operativa (America/Lima). La asigna el trigger desde service_day.';
COMMENT ON COLUMN topico.appointment.ticket_number IS 'Correlativo por sede y día; lo asigna la BD. Define el orden de la cola.';
COMMENT ON COLUMN topico.appointment.ticket_code IS 'Código visible del turno: prefijo de la sede + número (A-009).';
COMMENT ON COLUMN topico.appointment.channel IS 'Canal de la solicitud: PHONE, WALK_IN (presencial), WEB (Fase 2), MIGRATION (histórico).';
COMMENT ON COLUMN topico.appointment.origin_appointment_id IS 'Atención original cuando esta es una reprogramación.';
COMMENT ON COLUMN topico.appointment.admin_note IS 'Observación ADMINISTRATIVA. Prohibido registrar síntomas, diagnósticos u otra información clínica.';
COMMENT ON COLUMN topico.appointment.queued_at IS 'Momento en que la atención ingresó (o reingresó) a la cola EN_ESPERA.';
COMMENT ON COLUMN topico.appointment.call_count IS 'Número de veces que se llamó (incluye rellamados tras devolver a la cola).';
COMMENT ON COLUMN topico.appointment.closed_at IS 'Momento de cancelación, no presentación o anulación.';
COMMENT ON COLUMN topico.appointment.version IS 'Control de concurrencia optimista (lo gestiona el ORM).';

CREATE TABLE topico.appointment_event (
    id              bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    appointment_id  bigint       NOT NULL REFERENCES topico.appointment (id),
    action          varchar(20)  NOT NULL,
    from_status     varchar(15)  REFERENCES topico.appointment_status (code),
    to_status       varchar(15)  NOT NULL REFERENCES topico.appointment_status (code),
    reason_id       integer      REFERENCES topico.reason (id),
    note            varchar(300),
    occurred_at     timestamptz  NOT NULL DEFAULT now(),
    user_id         bigint       REFERENCES topico.app_user (id),
    ip              inet,
    request_id      varchar(40),
    CONSTRAINT ck_appointment_event_action CHECK (action IN (
        'REGISTER', 'ACTIVATE', 'CALL', 'REQUEUE', 'START', 'FINISH', 'CANCEL', 'NO_SHOW', 'VOID', 'MIGRATE')),
    CONSTRAINT ck_appointment_event_from CHECK ((action IN ('REGISTER', 'MIGRATE')) = (from_status IS NULL))
);
CREATE INDEX ix_appointment_event_appointment ON topico.appointment_event (appointment_id, occurred_at);
CREATE INDEX ix_appointment_event_occurred ON topico.appointment_event (occurred_at);
COMMENT ON TABLE  topico.appointment_event IS 'Historial inmutable de cambios de estado de cada atención (línea de tiempo).';
COMMENT ON COLUMN topico.appointment_event.user_id IS 'Usuario que ejecutó la acción; NULL para acciones automáticas del sistema.';

-- =============================================================================
-- 8. Notificaciones (patrón outbox)
-- =============================================================================

CREATE TABLE topico.notification_template (
    id           integer      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code         varchar(40)  NOT NULL,
    channel      varchar(10)  NOT NULL DEFAULT 'EMAIL',
    description  varchar(200) NOT NULL,
    subject      varchar(200) NOT NULL,
    body_text    text         NOT NULL,
    body_html    text,
    is_active    boolean      NOT NULL DEFAULT true,
    created_at   timestamptz  NOT NULL DEFAULT now(),
    updated_at   timestamptz  NOT NULL DEFAULT now(),
    updated_by   bigint       REFERENCES topico.app_user (id),
    CONSTRAINT uq_notification_template_code_channel UNIQUE (code, channel),
    CONSTRAINT ck_notification_template_channel CHECK (channel IN ('EMAIL')),
    CONSTRAINT ck_notification_template_code_format CHECK (code ~ '^[A-Z][A-Z0-9_]{1,39}$')
);
COMMENT ON TABLE topico.notification_template IS 'Plantillas editables (Jinja2 con sandbox) por evento y canal.';

CREATE TABLE topico.notification (
    id               bigint        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    appointment_id   bigint        REFERENCES topico.appointment (id),
    template_code    varchar(40)   NOT NULL,
    channel          varchar(10)   NOT NULL,
    recipient        varchar(254),
    subject          varchar(200),
    body_text        text,
    body_html        text,
    status           varchar(10)   NOT NULL DEFAULT 'PENDING',
    attempts         smallint      NOT NULL DEFAULT 0,
    max_attempts     smallint      NOT NULL DEFAULT 5,
    next_attempt_at  timestamptz   NOT NULL DEFAULT now(),
    last_error       varchar(1000),
    dedup_key        varchar(120),
    sent_at          timestamptz,
    created_at       timestamptz   NOT NULL DEFAULT now(),
    updated_at       timestamptz   NOT NULL DEFAULT now(),
    created_by       bigint        REFERENCES topico.app_user (id),
    CONSTRAINT uq_notification_dedup_key UNIQUE (dedup_key),
    CONSTRAINT ck_notification_channel CHECK (channel IN ('EMAIL')),
    CONSTRAINT ck_notification_status CHECK (status IN ('PENDING', 'SENDING', 'SENT', 'FAILED', 'SKIPPED', 'CANCELLED')),
    CONSTRAINT ck_notification_attempts CHECK (attempts >= 0 AND max_attempts BETWEEN 1 AND 20 AND attempts <= max_attempts),
    CONSTRAINT ck_notification_sent CHECK (status <> 'SENT' OR sent_at IS NOT NULL),
    CONSTRAINT ck_notification_recipient CHECK (status IN ('SKIPPED', 'CANCELLED') OR recipient IS NOT NULL)
);
CREATE INDEX ix_notification_pending ON topico.notification (next_attempt_at) WHERE status = 'PENDING';
CREATE INDEX ix_notification_appointment ON topico.notification (appointment_id);
CREATE INDEX ix_notification_status_created ON topico.notification (status, created_at DESC);
COMMENT ON TABLE  topico.notification IS 'Bandeja de salida (outbox). Se inserta en la misma transacción del evento y un worker la procesa con reintentos.';
COMMENT ON COLUMN topico.notification.dedup_key IS 'Evita notificaciones duplicadas del mismo evento (p. ej., APPT_UPCOMING:<id>).';
COMMENT ON COLUMN topico.notification.status IS 'SKIPPED: no se envía (p. ej., el trabajador no tiene correo). FAILED: agotó reintentos.';

-- =============================================================================
-- 9. Auditoría funcional (solo inserción + cadena de hash)
-- =============================================================================

CREATE TABLE topico.audit_event (
    id             bigint        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    chain_seq      bigint        NOT NULL,
    occurred_at    timestamptz   NOT NULL DEFAULT clock_timestamp(),
    user_id        bigint        REFERENCES topico.app_user (id),
    username       varchar(50),
    ip             inet,
    user_agent     varchar(500),
    request_id     varchar(40),
    action         varchar(60)   NOT NULL,
    resource_type  varchar(40),
    resource_id    varchar(64),
    site_id        integer       REFERENCES topico.site (id),
    result         varchar(10)   NOT NULL,
    reason         varchar(500),
    before_data    jsonb,
    after_data     jsonb,
    metadata       jsonb,
    prev_hash      char(64),
    hash           char(64)      NOT NULL,
    CONSTRAINT uq_audit_event_chain_seq UNIQUE (chain_seq),
    CONSTRAINT ck_audit_event_action_format CHECK (action ~ '^[A-Z][A-Z0-9_]{2,59}$'),
    CONSTRAINT ck_audit_event_result CHECK (result IN ('SUCCESS', 'DENIED', 'FAILURE')),
    CONSTRAINT ck_audit_event_hash_format CHECK (hash ~ '^[0-9a-f]{64}$')
);
CREATE INDEX ix_audit_event_occurred ON topico.audit_event (occurred_at DESC);
CREATE INDEX ix_audit_event_resource ON topico.audit_event (resource_type, resource_id);
CREATE INDEX ix_audit_event_user ON topico.audit_event (user_id, occurred_at DESC);
CREATE INDEX ix_audit_event_action ON topico.audit_event (action, occurred_at DESC);
COMMENT ON TABLE  topico.audit_event IS 'Auditoría funcional. Solo inserción; cada fila encadena el hash de la anterior (detección de alteraciones).';
COMMENT ON COLUMN topico.audit_event.chain_seq IS 'Posición en la cadena de hash (sin huecos). La asigna el trigger bajo bloqueo.';
COMMENT ON COLUMN topico.audit_event.username IS 'Copia del usuario al momento del evento (se conserva aunque el usuario cambie).';
COMMENT ON COLUMN topico.audit_event.before_data IS 'Valores anteriores (solo campos relevantes; nunca contraseñas ni tokens).';
COMMENT ON COLUMN topico.audit_event.hash IS 'SHA-256 del contenido del evento + prev_hash.';

-- =============================================================================
-- 10. Funciones de dominio y triggers
-- =============================================================================

-- ---- updated_at -----------------------------------------------------------
CREATE TRIGGER trg_app_user_updated_at BEFORE UPDATE ON topico.app_user
    FOR EACH ROW EXECUTE FUNCTION topico.tg_set_updated_at();
CREATE TRIGGER trg_role_updated_at BEFORE UPDATE ON topico.role
    FOR EACH ROW EXECUTE FUNCTION topico.tg_set_updated_at();
CREATE TRIGGER trg_site_updated_at BEFORE UPDATE ON topico.site
    FOR EACH ROW EXECUTE FUNCTION topico.tg_set_updated_at();
CREATE TRIGGER trg_system_parameter_updated_at BEFORE UPDATE ON topico.system_parameter
    FOR EACH ROW EXECUTE FUNCTION topico.tg_set_updated_at();
CREATE TRIGGER trg_site_schedule_updated_at BEFORE UPDATE ON topico.site_schedule
    FOR EACH ROW EXECUTE FUNCTION topico.tg_set_updated_at();
CREATE TRIGGER trg_import_batch_updated_at BEFORE UPDATE ON topico.import_batch
    FOR EACH ROW EXECUTE FUNCTION topico.tg_set_updated_at();
CREATE TRIGGER trg_department_updated_at BEFORE UPDATE ON topico.department
    FOR EACH ROW EXECUTE FUNCTION topico.tg_set_updated_at();
CREATE TRIGGER trg_worker_updated_at BEFORE UPDATE ON topico.worker
    FOR EACH ROW EXECUTE FUNCTION topico.tg_set_updated_at();
CREATE TRIGGER trg_worker_coverage_updated_at BEFORE UPDATE ON topico.worker_coverage
    FOR EACH ROW EXECUTE FUNCTION topico.tg_set_updated_at();
CREATE TRIGGER trg_reason_updated_at BEFORE UPDATE ON topico.reason
    FOR EACH ROW EXECUTE FUNCTION topico.tg_set_updated_at();
CREATE TRIGGER trg_service_day_updated_at BEFORE UPDATE ON topico.service_day
    FOR EACH ROW EXECUTE FUNCTION topico.tg_set_updated_at();
CREATE TRIGGER trg_notification_template_updated_at BEFORE UPDATE ON topico.notification_template
    FOR EACH ROW EXECUTE FUNCTION topico.tg_set_updated_at();
CREATE TRIGGER trg_notification_updated_at BEFORE UPDATE ON topico.notification
    FOR EACH ROW EXECUTE FUNCTION topico.tg_set_updated_at();

-- ---- Configuración por sede: una versión ya vigente es inmutable ------------
CREATE FUNCTION topico.tg_site_setting_version_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_today date;
BEGIN
    SELECT (now() AT TIME ZONE s.timezone)::date INTO v_today FROM topico.site s WHERE s.id = OLD.site_id;
    IF OLD.valid_from <= v_today THEN
        RAISE EXCEPTION 'La configuración vigente desde % ya está en uso; registre una nueva versión', OLD.valid_from
            USING ERRCODE = 'check_violation', CONSTRAINT = 'ck_site_setting_version_effective_immutable';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    IF NEW.site_id <> OLD.site_id THEN
        RAISE EXCEPTION 'No se puede cambiar la sede de una versión de configuración'
            USING ERRCODE = 'check_violation', CONSTRAINT = 'ck_site_setting_version_effective_immutable';
    END IF;
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;
CREATE TRIGGER trg_site_setting_version_guard BEFORE UPDATE OR DELETE ON topico.site_setting_version
    FOR EACH ROW EXECUTE FUNCTION topico.tg_site_setting_version_guard();

-- ---- Apertura del día operativo (congela la configuración vigente) ---------
CREATE FUNCTION topico.ensure_service_day(p_site_id integer, p_service_date date)
RETURNS bigint
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = topico, pg_temp
AS $$
DECLARE
    v_id  bigint;
    v_cfg topico.site_setting_version%ROWTYPE;
BEGIN
    SELECT id INTO v_id FROM topico.service_day WHERE site_id = p_site_id AND service_date = p_service_date;
    IF FOUND THEN
        RETURN v_id;
    END IF;

    SELECT * INTO v_cfg
      FROM topico.site_setting_version
     WHERE site_id = p_site_id AND valid_from <= p_service_date
     ORDER BY valid_from DESC
     LIMIT 1;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'La sede % no tiene configuración vigente para %', p_site_id, p_service_date
            USING ERRCODE = 'check_violation', CONSTRAINT = 'ck_service_day_setting_required';
    END IF;

    INSERT INTO topico.service_day (site_id, service_date, setting_version_id, capacity, slot_minutes,
                                    tolerance_minutes, max_concurrent_in_service)
    VALUES (p_site_id, p_service_date, v_cfg.id, v_cfg.daily_capacity, v_cfg.slot_minutes,
            v_cfg.tolerance_minutes, v_cfg.max_concurrent_in_service)
    ON CONFLICT (site_id, service_date) DO NOTHING
    RETURNING id INTO v_id;

    IF v_id IS NULL THEN  -- otra transacción lo creó en paralelo
        SELECT id INTO v_id FROM topico.service_day WHERE site_id = p_site_id AND service_date = p_service_date;
    END IF;
    RETURN v_id;
END;
$$;
COMMENT ON FUNCTION topico.ensure_service_day(integer, date) IS
    'Devuelve el día operativo de la sede; si no existe, lo crea congelando la configuración vigente. Seguro ante concurrencia.';

-- ---- Atención: numeración de turno y ocupación de cupo (INSERT) ------------
CREATE FUNCTION topico.tg_appointment_before_insert() RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = topico, pg_temp
AS $$
DECLARE
    v_day       topico.service_day%ROWTYPE;
    v_consumes  boolean;
    v_prefix    varchar(3);
BEGIN
    IF NEW.channel <> 'MIGRATION' AND NEW.status NOT IN ('REGISTRADO', 'EN_ESPERA') THEN
        RAISE EXCEPTION 'Una atención solo puede crearse en estado REGISTRADO o EN_ESPERA (recibido: %)', NEW.status
            USING ERRCODE = 'check_violation', CONSTRAINT = 'ck_appointment_initial_status';
    END IF;

    SELECT consumes_capacity INTO v_consumes FROM topico.appointment_status WHERE code = NEW.status;

    -- El UPDATE bloquea la fila del día: los registros concurrentes de la misma sede y fecha
    -- se serializan aquí. Si se supera la capacidad, falla ck_service_day_capacity.
    UPDATE topico.service_day d
       SET last_ticket_number = d.last_ticket_number + 1,
           occupied_count     = d.occupied_count + CASE WHEN coalesce(v_consumes, false) THEN 1 ELSE 0 END
     WHERE d.id = NEW.service_day_id
    RETURNING d.* INTO v_day;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'El día operativo % no existe', NEW.service_day_id
            USING ERRCODE = 'foreign_key_violation', CONSTRAINT = 'appointment_service_day_id_fkey';
    END IF;
    IF v_day.status <> 'OPEN' AND NEW.channel <> 'MIGRATION' THEN
        RAISE EXCEPTION 'El día operativo % está cerrado', v_day.service_date
            USING ERRCODE = 'check_violation', CONSTRAINT = 'ck_service_day_open';
    END IF;

    SELECT ticket_prefix INTO v_prefix FROM topico.site WHERE id = v_day.site_id;

    NEW.site_id       := v_day.site_id;
    NEW.service_date  := v_day.service_date;
    NEW.ticket_number := v_day.last_ticket_number;
    NEW.ticket_code   := v_prefix || '-' || lpad(v_day.last_ticket_number::text, 3, '0');
    IF NEW.status = 'EN_ESPERA' AND NEW.queued_at IS NULL THEN
        NEW.queued_at := NEW.registered_at;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER trg_appointment_before_insert BEFORE INSERT ON topico.appointment
    FOR EACH ROW EXECUTE FUNCTION topico.tg_appointment_before_insert();

-- ---- Atención: máquina de estados, inmutabilidad y liberación de cupo ------
CREATE FUNCTION topico.tg_appointment_before_update() RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = topico, pg_temp
AS $$
DECLARE
    v_old  topico.appointment_status%ROWTYPE;
    v_new  topico.appointment_status%ROWTYPE;
BEGIN
    IF NEW.public_id      IS DISTINCT FROM OLD.public_id
    OR NEW.service_day_id IS DISTINCT FROM OLD.service_day_id
    OR NEW.site_id        IS DISTINCT FROM OLD.site_id
    OR NEW.service_date   IS DISTINCT FROM OLD.service_date
    OR NEW.worker_id      IS DISTINCT FROM OLD.worker_id
    OR NEW.ticket_number  IS DISTINCT FROM OLD.ticket_number
    OR NEW.ticket_code    IS DISTINCT FROM OLD.ticket_code
    OR NEW.channel        IS DISTINCT FROM OLD.channel
    OR NEW.registered_at  IS DISTINCT FROM OLD.registered_at
    OR NEW.registered_by  IS DISTINCT FROM OLD.registered_by
    OR NEW.created_at     IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Se intentó modificar un campo inmutable de la atención %', OLD.id
            USING ERRCODE = 'check_violation', CONSTRAINT = 'ck_appointment_immutable_fields';
    END IF;

    SELECT * INTO v_old FROM topico.appointment_status WHERE code = OLD.status;

    IF v_old.is_final THEN
        RAISE EXCEPTION 'La atención % está en estado final (%) y no puede modificarse', OLD.id, OLD.status
            USING ERRCODE = 'check_violation', CONSTRAINT = 'ck_appointment_final_immutable';
    END IF;

    IF NEW.status IS DISTINCT FROM OLD.status THEN
        IF NOT EXISTS (SELECT 1 FROM topico.appointment_status_transition t
                        WHERE t.from_status = OLD.status AND t.to_status = NEW.status) THEN
            RAISE EXCEPTION 'Transición de estado no permitida: % → %', OLD.status, NEW.status
                USING ERRCODE = 'check_violation', CONSTRAINT = 'ck_appointment_status_transition';
        END IF;

        SELECT * INTO v_new FROM topico.appointment_status WHERE code = NEW.status;

        IF v_old.consumes_capacity IS DISTINCT FROM v_new.consumes_capacity THEN
            UPDATE topico.service_day
               SET occupied_count = occupied_count + CASE WHEN v_new.consumes_capacity THEN 1 ELSE -1 END
             WHERE id = OLD.service_day_id;
        END IF;
    END IF;

    NEW.updated_at := now();
    RETURN NEW;
END;
$$;
CREATE TRIGGER trg_appointment_before_update BEFORE UPDATE ON topico.appointment
    FOR EACH ROW EXECUTE FUNCTION topico.tg_appointment_before_update();

-- Sin borrado físico de atenciones, días operativos, eventos ni auditoría.
CREATE TRIGGER trg_appointment_forbid_delete BEFORE DELETE ON topico.appointment
    FOR EACH ROW EXECUTE FUNCTION topico.tg_forbid_change();
CREATE TRIGGER trg_appointment_forbid_truncate BEFORE TRUNCATE ON topico.appointment
    FOR EACH STATEMENT EXECUTE FUNCTION topico.tg_forbid_change();
CREATE TRIGGER trg_service_day_forbid_delete BEFORE DELETE ON topico.service_day
    FOR EACH ROW EXECUTE FUNCTION topico.tg_forbid_change();
CREATE TRIGGER trg_appointment_event_forbid_change BEFORE UPDATE OR DELETE ON topico.appointment_event
    FOR EACH ROW EXECUTE FUNCTION topico.tg_forbid_change();
CREATE TRIGGER trg_appointment_event_forbid_truncate BEFORE TRUNCATE ON topico.appointment_event
    FOR EACH STATEMENT EXECUTE FUNCTION topico.tg_forbid_change();

-- ---- Auditoría: cadena de hash ------------------------------------------------
CREATE FUNCTION topico.audit_event_compute_hash(e topico.audit_event) RETURNS char(64)
LANGUAGE sql STABLE AS $$
    SELECT encode(sha256(convert_to(concat_ws('|',
        e.chain_seq::text,
        (extract(epoch FROM e.occurred_at))::numeric(20, 6)::text,
        coalesce(e.user_id::text, ''),
        coalesce(e.username, ''),
        coalesce(host(e.ip), ''),
        coalesce(e.request_id, ''),
        e.action,
        coalesce(e.resource_type, ''),
        coalesce(e.resource_id, ''),
        coalesce(e.site_id::text, ''),
        e.result,
        coalesce(e.reason, ''),
        coalesce(e.before_data::text, ''),
        coalesce(e.after_data::text, ''),
        coalesce(e.metadata::text, ''),
        coalesce(e.prev_hash, '')), 'UTF8')), 'hex');
$$;
COMMENT ON FUNCTION topico.audit_event_compute_hash(topico.audit_event) IS 'Hash canónico de un evento de auditoría.';

CREATE FUNCTION topico.tg_audit_event_before_insert() RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = topico, pg_temp
AS $$
DECLARE
    v_last_seq  bigint;
    v_last_hash char(64);
BEGIN
    -- Serializa la construcción de la cadena (el bloqueo se libera al terminar la transacción).
    PERFORM pg_advisory_xact_lock(hashtext('topico.audit_event.chain'));

    SELECT chain_seq, hash INTO v_last_seq, v_last_hash
      FROM topico.audit_event ORDER BY chain_seq DESC LIMIT 1;

    NEW.chain_seq   := coalesce(v_last_seq, 0) + 1;
    NEW.prev_hash   := v_last_hash;
    NEW.occurred_at := clock_timestamp();
    NEW.hash        := topico.audit_event_compute_hash(NEW);
    RETURN NEW;
END;
$$;
CREATE TRIGGER trg_audit_event_before_insert BEFORE INSERT ON topico.audit_event
    FOR EACH ROW EXECUTE FUNCTION topico.tg_audit_event_before_insert();
CREATE TRIGGER trg_audit_event_forbid_change BEFORE UPDATE OR DELETE ON topico.audit_event
    FOR EACH ROW EXECUTE FUNCTION topico.tg_forbid_change();
CREATE TRIGGER trg_audit_event_forbid_truncate BEFORE TRUNCATE ON topico.audit_event
    FOR EACH STATEMENT EXECUTE FUNCTION topico.tg_forbid_change();

CREATE FUNCTION topico.verify_audit_chain()
RETURNS TABLE (chain_seq bigint, problem text)
LANGUAGE plpgsql STABLE
SET search_path = topico, pg_temp
AS $$
DECLARE
    r           topico.audit_event;
    v_prev      char(64) := NULL;
    v_expected  bigint := 1;
BEGIN
    FOR r IN SELECT * FROM topico.audit_event a ORDER BY a.chain_seq LOOP
        IF r.chain_seq <> v_expected THEN
            chain_seq := r.chain_seq; problem := 'SEQUENCE_GAP'; RETURN NEXT;
        END IF;
        IF r.prev_hash IS DISTINCT FROM v_prev THEN
            chain_seq := r.chain_seq; problem := 'PREV_HASH_MISMATCH'; RETURN NEXT;
        END IF;
        IF r.hash <> topico.audit_event_compute_hash(r) THEN
            chain_seq := r.chain_seq; problem := 'HASH_MISMATCH'; RETURN NEXT;
        END IF;
        v_prev := r.hash;
        v_expected := r.chain_seq + 1;
    END LOOP;
END;
$$;
COMMENT ON FUNCTION topico.verify_audit_chain() IS
    'Verifica la integridad de la auditoría. Sin filas = íntegra. Devuelve huecos o hashes alterados.';

-- =============================================================================
-- 11. Privilegios (mínimo privilegio para topico_app)
-- =============================================================================

GRANT USAGE ON SCHEMA topico TO topico_app, topico_readonly;

REVOKE ALL ON ALL TABLES IN SCHEMA topico FROM topico_app, topico_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA topico TO topico_app, topico_readonly;

-- Tablas administradas por la aplicación (sin DELETE: se desactivan)
GRANT INSERT, UPDATE ON
    topico.app_user, topico.role, topico.site, topico.system_parameter,
    topico.site_setting_version, topico.site_schedule,
    topico.import_batch, topico.department, topico.insurer, topico.worker, topico.worker_coverage,
    topico.reason, topico.notification_template, topico.notification
TO topico_app;

-- Tablas puente / efímeras donde el borrado es legítimo
GRANT INSERT, DELETE ON topico.role_permission, topico.user_role, topico.user_site TO topico_app;
GRANT INSERT, UPDATE, DELETE ON topico.refresh_token, topico.site_closure TO topico_app;

-- Staging de importación: se escribe una vez
GRANT INSERT ON topico.import_row TO topico_app;

-- Solo inserción
GRANT INSERT ON topico.appointment_event, topico.audit_event TO topico_app;

-- Día operativo: los contadores solo los modifican los triggers (SECURITY DEFINER)
GRANT UPDATE (status, capacity, closed_at, closed_by,
              capacity_adjusted_at, capacity_adjusted_by, capacity_adjust_reason, updated_at)
    ON topico.service_day TO topico_app;

-- Atención: INSERT libre (los triggers asignan turno/sede/fecha); UPDATE solo de columnas de ciclo de vida
GRANT INSERT ON topico.appointment TO topico_app;
GRANT UPDATE (status, admin_note, queued_at, called_at, called_by, call_count,
              started_at, started_by, finished_at, finished_by,
              closed_at, closed_by, close_reason_id, close_note, version, updated_at)
    ON topico.appointment TO topico_app;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA topico TO topico_app;

REVOKE ALL ON FUNCTION topico.ensure_service_day(integer, date) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION topico.ensure_service_day(integer, date) TO topico_app;
GRANT EXECUTE ON FUNCTION topico.verify_audit_chain() TO topico_app, topico_readonly;
