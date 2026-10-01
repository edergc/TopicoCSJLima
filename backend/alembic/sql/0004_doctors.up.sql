-- Revisión 0004: médicos del tópico por sede y médico que realizó cada atención.
-- Solo datos administrativos del profesional (nombre, CMP, especialidad); ningún dato clínico.
SET search_path TO topico, public;

CREATE TABLE topico.doctor (
    id               integer      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    site_id          integer      NOT NULL REFERENCES topico.site (id),
    full_name        varchar(150) NOT NULL,
    document_number  varchar(8),
    cmp              varchar(6),
    specialty        varchar(80),
    phone            varchar(20),
    email            varchar(150),
    is_active        boolean      NOT NULL DEFAULT true,
    created_at       timestamptz  NOT NULL DEFAULT now(),
    updated_at       timestamptz  NOT NULL DEFAULT now(),
    created_by       bigint       REFERENCES topico.app_user (id),
    updated_by       bigint       REFERENCES topico.app_user (id),
    CONSTRAINT ck_doctor_name_not_blank CHECK (btrim(full_name) <> ''),
    CONSTRAINT ck_doctor_document_format CHECK (document_number IS NULL OR document_number ~ '^[0-9]{8}$'),
    CONSTRAINT ck_doctor_cmp_format CHECK (cmp IS NULL OR cmp ~ '^[0-9]{1,6}$')
);
CREATE UNIQUE INDEX uq_doctor_site_cmp ON topico.doctor (site_id, cmp) WHERE cmp IS NOT NULL;
CREATE UNIQUE INDEX uq_doctor_site_document ON topico.doctor (site_id, document_number) WHERE document_number IS NOT NULL;
CREATE INDEX ix_doctor_site_active ON topico.doctor (site_id) WHERE is_active;

COMMENT ON TABLE topico.doctor IS 'Médicos que atienden en el tópico de cada sede. No se eliminan: se desactivan.';
COMMENT ON COLUMN topico.doctor.full_name IS 'Nombre completo del profesional, tal como se muestra (p. ej., "Dra. Ana Pérez Soto").';
COMMENT ON COLUMN topico.doctor.document_number IS 'DNI del profesional (opcional).';
COMMENT ON COLUMN topico.doctor.cmp IS 'Número de colegiatura del Colegio Médico del Perú (opcional, único por sede).';
COMMENT ON COLUMN topico.doctor.specialty IS 'Especialidad (opcional), p. ej. Medicina General.';
COMMENT ON COLUMN topico.doctor.is_active IS 'Solo los médicos activos pueden asignarse a nuevas atenciones.';

CREATE TRIGGER trg_doctor_updated_at BEFORE UPDATE ON topico.doctor
    FOR EACH ROW EXECUTE FUNCTION topico.tg_set_updated_at();

ALTER TABLE topico.appointment ADD COLUMN doctor_id integer REFERENCES topico.doctor (id);
COMMENT ON COLUMN topico.appointment.doctor_id IS 'Médico que realizó la atención (se asigna al iniciarla).';
CREATE INDEX ix_appointment_doctor ON topico.appointment (doctor_id) WHERE doctor_id IS NOT NULL;

GRANT SELECT ON topico.doctor TO topico_app, topico_readonly;
GRANT INSERT, UPDATE ON topico.doctor TO topico_app;
GRANT UPDATE (doctor_id) ON topico.appointment TO topico_app;
