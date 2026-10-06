-- Revisión 0005: sedes y consultorios administrables.
--   * Permiso site:manage (crear sedes nuevas) para el rol ADMIN.
--   * Consultorios por sede y consultorio al que se llama a cada atención.
SET search_path TO topico, public;

INSERT INTO topico.permission (code, module, description) VALUES
    ('site:manage', 'sites', 'Crear sedes nuevas y activarlas o desactivarlas');

INSERT INTO topico.role_permission (role_id, permission_id)
SELECT r.id, p.id FROM topico.role r, topico.permission p
 WHERE r.code = 'ADMIN' AND p.code = 'site:manage';

CREATE TABLE topico.consulting_room (
    id             integer      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    site_id        integer      NOT NULL REFERENCES topico.site (id),
    name           varchar(60)  NOT NULL,
    location_note  varchar(150),
    sort_order     smallint     NOT NULL DEFAULT 0,
    is_active      boolean      NOT NULL DEFAULT true,
    created_at     timestamptz  NOT NULL DEFAULT now(),
    updated_at     timestamptz  NOT NULL DEFAULT now(),
    created_by     bigint       REFERENCES topico.app_user (id),
    updated_by     bigint       REFERENCES topico.app_user (id),
    CONSTRAINT ck_consulting_room_name_not_blank CHECK (btrim(name) <> '')
);
CREATE UNIQUE INDEX uq_consulting_room_site_name ON topico.consulting_room (site_id, lower(name));
CREATE INDEX ix_consulting_room_site_active ON topico.consulting_room (site_id) WHERE is_active;

COMMENT ON TABLE topico.consulting_room IS 'Consultorios del tópico de cada sede. No se eliminan: se desactivan.';
COMMENT ON COLUMN topico.consulting_room.name IS 'Nombre visible en la pantalla de sala y en el correo de llamado (p. ej., "Consultorio 1").';
COMMENT ON COLUMN topico.consulting_room.location_note IS 'Indicación de ubicación (p. ej., "Primer piso, al fondo").';
COMMENT ON COLUMN topico.consulting_room.sort_order IS 'Orden de presentación.';

CREATE TRIGGER trg_consulting_room_updated_at BEFORE UPDATE ON topico.consulting_room
    FOR EACH ROW EXECUTE FUNCTION topico.tg_set_updated_at();

ALTER TABLE topico.appointment ADD COLUMN room_id integer REFERENCES topico.consulting_room (id);
COMMENT ON COLUMN topico.appointment.room_id IS 'Consultorio al que se llamó a la persona (se asigna al llamar).';
CREATE INDEX ix_appointment_room ON topico.appointment (room_id) WHERE room_id IS NOT NULL;

GRANT SELECT ON topico.consulting_room TO topico_app, topico_readonly;
GRANT INSERT, UPDATE ON topico.consulting_room TO topico_app;
GRANT UPDATE (room_id) ON topico.appointment TO topico_app;
