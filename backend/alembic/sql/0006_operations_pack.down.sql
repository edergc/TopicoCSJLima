-- Reversión de la revisión 0006.
SET search_path TO topico, public;

DELETE FROM topico.system_parameter WHERE key IN
    ('capacity.by_doctor_schedule', 'rating.enabled', 'rating.valid_days', 'day_close.send_summary', 'display.message_seconds');
DROP TABLE topico.display_message;
DROP TABLE topico.service_rating;
DELETE FROM topico.notification_template WHERE code IN ('DAY_SUMMARY', 'RATING_REQUEST');
ALTER TABLE topico.notification
    DROP CONSTRAINT ck_notification_attachment,
    DROP COLUMN attachment_name,
    DROP COLUMN attachment_type,
    DROP COLUMN attachment_data;
DELETE FROM topico.reason WHERE type = 'NO_SHOW' AND code = 'CIERRE_JORNADA';
DELETE FROM topico.appointment_status_transition WHERE action = 'CLOSE_DAY';
ALTER TABLE topico.appointment_event DROP CONSTRAINT ck_appointment_event_action;
ALTER TABLE topico.appointment_event ADD CONSTRAINT ck_appointment_event_action CHECK (action IN (
    'REGISTER', 'ACTIVATE', 'CALL', 'REQUEUE', 'START', 'FINISH', 'CANCEL', 'NO_SHOW', 'VOID', 'MIGRATE'));
ALTER TABLE topico.appointment DROP CONSTRAINT ck_appointment_called_data;
ALTER TABLE topico.appointment ADD CONSTRAINT ck_appointment_called_data CHECK (
    status NOT IN ('LLAMADO', 'NO_PRESENTADO') OR channel = 'MIGRATION'
    OR (called_at IS NOT NULL AND called_by IS NOT NULL));
DROP TABLE topico.site_pause;
DROP TABLE topico.doctor_absence;
DROP TABLE topico.doctor_schedule;
