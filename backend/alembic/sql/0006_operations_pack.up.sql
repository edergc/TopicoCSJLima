-- Revisión 0006: paquete operativo.
--   2.1 Horario y ausencias por médico (la capacidad del día puede calcularse con los médicos presentes).
--   2.3 Pausa del tópico.
--   2.4 Cierre del día (pendientes → no presentado) y resumen PDF por correo (adjuntos en el outbox).
--   2.6 Calificación anónima del servicio.
--   2.7 Mensajes rotativos de la pantalla de sala.
SET search_path TO topico, public;

-- =============================================================================
-- 2.1 Horario y ausencias por médico
-- =============================================================================
CREATE TABLE topico.doctor_schedule (
    id          bigint    GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    doctor_id   integer   NOT NULL REFERENCES topico.doctor (id),
    weekday     smallint  NOT NULL,
    start_time  time      NOT NULL,
    end_time    time      NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    created_by  bigint    REFERENCES topico.app_user (id),
    CONSTRAINT ck_doctor_schedule_weekday CHECK (weekday BETWEEN 1 AND 7),
    CONSTRAINT ck_doctor_schedule_times CHECK (end_time > start_time)
);
CREATE INDEX ix_doctor_schedule_doctor ON topico.doctor_schedule (doctor_id, weekday);
COMMENT ON TABLE topico.doctor_schedule IS 'Horario semanal de cada médico (bloques por día; se reemplaza completo y queda auditado). Sin bloques = disponible en todo el horario de la sede.';
COMMENT ON COLUMN topico.doctor_schedule.weekday IS '1 = lunes … 7 = domingo.';

CREATE TABLE topico.doctor_absence (
    id          bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    doctor_id   integer      NOT NULL REFERENCES topico.doctor (id),
    date_from   date         NOT NULL,
    date_to     date         NOT NULL,
    reason      varchar(150) NOT NULL,
    created_at  timestamptz  NOT NULL DEFAULT now(),
    created_by  bigint       REFERENCES topico.app_user (id),
    CONSTRAINT ck_doctor_absence_range CHECK (date_to >= date_from),
    CONSTRAINT ck_doctor_absence_reason CHECK (btrim(reason) <> '')
);
CREATE INDEX ix_doctor_absence_doctor ON topico.doctor_absence (doctor_id, date_from, date_to);
COMMENT ON TABLE topico.doctor_absence IS 'Ausencias del médico (vacaciones, licencia, capacitación). Lo ausentan del día y reducen la capacidad calculada.';
COMMENT ON COLUMN topico.doctor_absence.reason IS 'Motivo administrativo (sin datos clínicos del profesional).';

-- =============================================================================
-- 2.3 Pausa del tópico
-- =============================================================================
CREATE TABLE topico.site_pause (
    id            bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    site_id       integer      NOT NULL REFERENCES topico.site (id),
    started_at    timestamptz  NOT NULL,
    resume_at     timestamptz  NOT NULL,
    ended_at      timestamptz,
    reason        varchar(150) NOT NULL,
    created_by    bigint       REFERENCES topico.app_user (id),
    ended_by      bigint       REFERENCES topico.app_user (id),
    created_at    timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT ck_site_pause_resume CHECK (resume_at > started_at),
    CONSTRAINT ck_site_pause_ended CHECK (ended_at IS NULL OR ended_at >= started_at),
    CONSTRAINT ck_site_pause_reason CHECK (btrim(reason) <> '')
);
CREATE UNIQUE INDEX uq_site_pause_active ON topico.site_pause (site_id) WHERE ended_at IS NULL;
COMMENT ON TABLE topico.site_pause IS 'Pausas de la atención del tópico (refrigerio, emergencia, reunión). Una sola activa por sede.';
COMMENT ON COLUMN topico.site_pause.resume_at IS 'Hora prevista de reanudación (se muestra en la pantalla de sala y desplaza las horas estimadas).';

-- =============================================================================
-- 2.4 Cierre del día
-- =============================================================================
INSERT INTO topico.appointment_status_transition (from_status, to_status, action) VALUES
    ('REGISTRADO', 'NO_PRESENTADO', 'CLOSE_DAY'),
    ('EN_ESPERA',  'NO_PRESENTADO', 'CLOSE_DAY');

-- Al cerrar el día, quienes nunca fueron llamados pasan a NO_PRESENTADO sin datos de llamado
-- (no se inventa un llamado). El llamado sigue siendo obligatorio para el estado LLAMADO.
ALTER TABLE topico.appointment DROP CONSTRAINT ck_appointment_called_data;
ALTER TABLE topico.appointment ADD CONSTRAINT ck_appointment_called_data CHECK (
    status <> 'LLAMADO' OR channel = 'MIGRATION' OR (called_at IS NOT NULL AND called_by IS NOT NULL));

ALTER TABLE topico.appointment_event DROP CONSTRAINT ck_appointment_event_action;
ALTER TABLE topico.appointment_event ADD CONSTRAINT ck_appointment_event_action CHECK (action IN (
    'REGISTER', 'ACTIVATE', 'CALL', 'REQUEUE', 'START', 'FINISH', 'CANCEL', 'NO_SHOW', 'VOID', 'MIGRATE', 'CLOSE_DAY'));

INSERT INTO topico.reason (type, code, label, requires_note, sort_order) VALUES
    ('NO_SHOW', 'CIERRE_JORNADA', 'No fue atendido al cierre de la jornada', false, 90);

ALTER TABLE topico.notification
    ADD COLUMN attachment_name varchar(150),
    ADD COLUMN attachment_type varchar(80),
    ADD COLUMN attachment_data bytea,
    ADD CONSTRAINT ck_notification_attachment CHECK (
        (attachment_data IS NULL AND attachment_name IS NULL)
        OR (attachment_data IS NOT NULL AND attachment_name IS NOT NULL AND attachment_type IS NOT NULL
            AND octet_length(attachment_data) <= 5242880));
COMMENT ON COLUMN topico.notification.attachment_data IS 'Adjunto opcional (p. ej., PDF del resumen del día), máximo 5 MB.';

INSERT INTO topico.notification_template (code, channel, description, subject, body_text) VALUES
('DAY_SUMMARY', 'EMAIL', 'Resumen del día al cerrar la jornada (a supervisión)',
 'Tópico de Salud: resumen del {{ service_date }} – {{ site_name }}',
 'Se cerró la jornada del Tópico de Salud.

  Sede:          {{ site_name }}
  Fecha:         {{ service_date }}
  Atendidos:     {{ attended }}
  No presentados: {{ no_show }}
  Cancelados:    {{ cancelled }}
  Cerrado por:   {{ closed_by }}

Se adjunta el reporte del día en PDF.

{{ institution_name }}
Este es un mensaje automático; por favor no responda a este correo.'),
('RATING_REQUEST', 'EMAIL', 'Invitación a calificar la atención (anónima)',
 'Tópico de Salud: ¿cómo fue su atención?',
 'Estimado(a) {{ worker_first_name }}:

Gracias por acudir al Tópico de Salud ({{ site_name }}).
Nos ayudaría mucho que califique el trato y el tiempo de espera de su atención.
Le tomará menos de un minuto y su respuesta es anónima:

  {{ rating_url }}

El enlace vence en {{ rating_valid_days }} días.

{{ institution_name }}
Este es un mensaje automático; por favor no responda a este correo.');

-- =============================================================================
-- 2.6 Calificación del servicio (anónima)
-- =============================================================================
CREATE TABLE topico.service_rating (
    id              bigint        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    appointment_id  bigint        NOT NULL REFERENCES topico.appointment (id),
    site_id         integer       NOT NULL REFERENCES topico.site (id),
    service_date    date          NOT NULL,
    doctor_id       integer       REFERENCES topico.doctor (id),
    token_hash      char(64)      NOT NULL,
    expires_at      timestamptz   NOT NULL,
    score           smallint,
    wait_score      smallint,
    comment         varchar(500),
    submitted_at    timestamptz,
    created_at      timestamptz   NOT NULL DEFAULT now(),
    CONSTRAINT uq_service_rating_appointment UNIQUE (appointment_id),
    CONSTRAINT uq_service_rating_token UNIQUE (token_hash),
    CONSTRAINT ck_service_rating_score CHECK (score IS NULL OR score BETWEEN 1 AND 5),
    CONSTRAINT ck_service_rating_wait CHECK (wait_score IS NULL OR wait_score BETWEEN 1 AND 5),
    CONSTRAINT ck_service_rating_submitted CHECK ((submitted_at IS NULL) = (score IS NULL))
);
CREATE INDEX ix_service_rating_site_date ON topico.service_rating (site_id, service_date) WHERE submitted_at IS NOT NULL;
COMMENT ON TABLE topico.service_rating IS 'Calificación anónima del servicio (trato y tiempo de espera; nunca datos de salud). Los reportes solo muestran agregados y comentarios sin identificar.';
COMMENT ON COLUMN topico.service_rating.token_hash IS 'SHA-256 del enlace enviado por correo; el enlace no se guarda.';
COMMENT ON COLUMN topico.service_rating.appointment_id IS 'Solo para impedir más de una calificación por atención; nunca se expone.';

-- =============================================================================
-- 2.7 Mensajes de la pantalla de sala
-- =============================================================================
CREATE TABLE topico.display_message (
    id          integer      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    site_id     integer      REFERENCES topico.site (id),
    text        varchar(200) NOT NULL,
    valid_from  date         NOT NULL,
    valid_to    date,
    sort_order  smallint     NOT NULL DEFAULT 0,
    is_active   boolean      NOT NULL DEFAULT true,
    created_at  timestamptz  NOT NULL DEFAULT now(),
    updated_at  timestamptz  NOT NULL DEFAULT now(),
    created_by  bigint       REFERENCES topico.app_user (id),
    updated_by  bigint       REFERENCES topico.app_user (id),
    CONSTRAINT ck_display_message_text CHECK (btrim(text) <> ''),
    CONSTRAINT ck_display_message_range CHECK (valid_to IS NULL OR valid_to >= valid_from)
);
COMMENT ON TABLE topico.display_message IS 'Mensajes que rotan al pie de la pantalla de sala. site_id NULL = todas las sedes.';
CREATE TRIGGER trg_display_message_updated_at BEFORE UPDATE ON topico.display_message
    FOR EACH ROW EXECUTE FUNCTION topico.tg_set_updated_at();

-- =============================================================================
-- Parámetros
-- =============================================================================
INSERT INTO topico.system_parameter (key, value, value_type, description, is_editable) VALUES
    ('capacity.by_doctor_schedule', 'true'::jsonb, 'bool', 'Calcula la capacidad del día con los médicos presentes (según su horario y ausencias), sin superar la capacidad configurada de la sede. Solo aplica si algún médico de la sede tiene horario.', true),
    ('rating.enabled',              'true'::jsonb, 'bool', 'Envía al finalizar la atención un enlace para calificar el servicio (anónimo).', true),
    ('rating.valid_days',           '7'::jsonb,    'int',  'Días de vigencia del enlace de calificación.', true),
    ('day_close.send_summary',      'true'::jsonb, 'bool', 'Al cerrar el día, envía el resumen en PDF a las supervisoras de la sede.', true),
    ('display.message_seconds',     '10'::jsonb,   'int',  'Segundos que se muestra cada mensaje rotativo en la pantalla de sala.', true);

-- =============================================================================
-- Privilegios
-- =============================================================================
GRANT SELECT ON topico.doctor_schedule, topico.doctor_absence, topico.site_pause,
                topico.service_rating, topico.display_message TO topico_app, topico_readonly;
GRANT INSERT, DELETE ON topico.doctor_schedule TO topico_app;
GRANT INSERT, DELETE ON topico.doctor_absence TO topico_app;
GRANT INSERT ON topico.site_pause TO topico_app;
GRANT UPDATE (ended_at, ended_by) ON topico.site_pause TO topico_app;
GRANT INSERT ON topico.service_rating TO topico_app;
GRANT UPDATE (score, wait_score, comment, submitted_at) ON topico.service_rating TO topico_app;
GRANT INSERT, UPDATE ON topico.display_message TO topico_app;
