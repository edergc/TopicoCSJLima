-- Reversión de la revisión 0007.
SET search_path TO topico, public;

DELETE FROM topico.system_parameter WHERE key IN
    ('priority.enabled', 'priority.max_consecutive', 'branding.org_name', 'branding.primary_color');
DROP TABLE topico.brand_asset;
ALTER TABLE topico.appointment_event DROP CONSTRAINT ck_appointment_event_action;
ALTER TABLE topico.appointment_event ADD CONSTRAINT ck_appointment_event_action CHECK (action IN (
    'REGISTER', 'ACTIVATE', 'CALL', 'REQUEUE', 'START', 'FINISH', 'CANCEL', 'NO_SHOW', 'VOID', 'MIGRATE', 'CLOSE_DAY'));
ALTER TABLE topico.appointment
    DROP CONSTRAINT ck_appointment_priority_data,
    DROP COLUMN priority_set_by,
    DROP COLUMN priority_set_at,
    DROP COLUMN priority_reason_id;
DELETE FROM topico.reason WHERE type = 'PRIORITY';
ALTER TABLE topico.reason DROP CONSTRAINT ck_reason_type;
ALTER TABLE topico.reason ADD CONSTRAINT ck_reason_type CHECK (type IN ('CANCEL', 'VOID', 'NO_SHOW', 'REQUEUE'));
