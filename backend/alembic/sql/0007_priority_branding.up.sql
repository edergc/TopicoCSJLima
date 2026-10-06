-- Revisión 0007:
--   * Prioridad explícita y auditable (desactivada por defecto). Requerimiento §11: «Si en el futuro se
--     requiere prioridad especial, deberá diseñarse como una regla explícita y auditable».
--   * Identidad visual configurable (logo y color institucional) para la interfaz, correos y PDF.
SET search_path TO topico, public;

-- =============================================================================
-- Prioridad
-- =============================================================================
ALTER TABLE topico.reason DROP CONSTRAINT ck_reason_type;
ALTER TABLE topico.reason ADD CONSTRAINT ck_reason_type
    CHECK (type IN ('CANCEL', 'VOID', 'NO_SHOW', 'REQUEUE', 'PRIORITY'));

-- Categorías de prioridad (solo la categoría: nunca diagnósticos ni detalles de salud)
INSERT INTO topico.reason (type, code, label, requires_note, sort_order) VALUES
    ('PRIORITY', 'GESTANTE',     'Gestante',                         false, 10),
    ('PRIORITY', 'ADULTO_MAYOR', 'Adulto mayor (60 años o más)',     false, 20),
    ('PRIORITY', 'DISCAPACIDAD', 'Persona con discapacidad',         false, 30);

ALTER TABLE topico.appointment
    ADD COLUMN priority_reason_id integer REFERENCES topico.reason (id),
    ADD COLUMN priority_set_at    timestamptz,
    ADD COLUMN priority_set_by    bigint REFERENCES topico.app_user (id),
    ADD CONSTRAINT ck_appointment_priority_data CHECK (
        priority_reason_id IS NULL OR (priority_set_at IS NOT NULL AND priority_set_by IS NOT NULL));
COMMENT ON COLUMN topico.appointment.priority_reason_id IS
    'Categoría de atención prioritaria (regla explícita, auditada). NULL = orden normal de registro.';

ALTER TABLE topico.appointment_event DROP CONSTRAINT ck_appointment_event_action;
ALTER TABLE topico.appointment_event ADD CONSTRAINT ck_appointment_event_action CHECK (action IN (
    'REGISTER', 'ACTIVATE', 'CALL', 'REQUEUE', 'START', 'FINISH', 'CANCEL', 'NO_SHOW', 'VOID', 'MIGRATE',
    'CLOSE_DAY', 'PRIORITY'));

GRANT UPDATE (priority_reason_id, priority_set_at, priority_set_by) ON topico.appointment TO topico_app;

-- =============================================================================
-- Identidad visual
-- =============================================================================
CREATE TABLE topico.brand_asset (
    code          varchar(20)  PRIMARY KEY,
    content_type  varchar(40)  NOT NULL,
    data          bytea        NOT NULL,
    updated_at    timestamptz  NOT NULL DEFAULT now(),
    updated_by    bigint       REFERENCES topico.app_user (id),
    CONSTRAINT ck_brand_asset_code CHECK (code IN ('LOGO')),
    CONSTRAINT ck_brand_asset_type CHECK (content_type IN ('image/png', 'image/jpeg')),
    CONSTRAINT ck_brand_asset_size CHECK (octet_length(data) <= 524288)
);
COMMENT ON TABLE topico.brand_asset IS 'Recursos de identidad visual (logo institucional PNG/JPEG, máx. 512 KB).';
GRANT SELECT ON topico.brand_asset TO topico_app, topico_readonly;
GRANT INSERT, UPDATE, DELETE ON topico.brand_asset TO topico_app;

-- =============================================================================
-- Parámetros
-- =============================================================================
INSERT INTO topico.system_parameter (key, value, value_type, description, is_editable) VALUES
    ('priority.enabled',         'false'::jsonb, 'bool', 'Habilita la atención prioritaria (gestantes, adultos mayores, personas con discapacidad). Desactivada: la cola respeta estrictamente el orden de registro.', true),
    ('priority.max_consecutive', '3'::jsonb,     'int',  'Máximo de llamados prioritarios seguidos antes de llamar a una persona en orden normal (evita esperas indefinidas).', true),
    ('branding.org_name',        '"Poder Judicial del Perú"'::jsonb, 'string', 'Nombre de la organización (encabezado de la interfaz, correos y PDF).', true),
    ('branding.primary_color',   '"#7a1e2c"'::jsonb, 'string', 'Color institucional principal en formato #RRGGBB (interfaz, correos y PDF).', true);
