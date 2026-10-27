-- Revisión 0010: el consultorio se asigna al llamar (el primero libre) y se puede reasignar.
--   Cada reasignación queda en la línea de tiempo como ROOM_CHANGE (sin cambio de estado).
SET search_path TO topico, public;

ALTER TABLE topico.appointment_event DROP CONSTRAINT ck_appointment_event_action;
ALTER TABLE topico.appointment_event ADD CONSTRAINT ck_appointment_event_action CHECK (action IN (
    'REGISTER', 'ACTIVATE', 'CALL', 'REQUEUE', 'START', 'FINISH', 'CANCEL', 'NO_SHOW', 'VOID', 'MIGRATE',
    'CLOSE_DAY', 'PRIORITY', 'ROOM_CHANGE'));
