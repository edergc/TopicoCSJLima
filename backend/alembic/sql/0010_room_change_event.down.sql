SET search_path TO topico, public;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM topico.appointment_event WHERE action = 'ROOM_CHANGE') THEN
        RAISE EXCEPTION 'Hay cambios de consultorio registrados: no se puede revertir 0010.';
    END IF;
END $$;

ALTER TABLE topico.appointment_event DROP CONSTRAINT ck_appointment_event_action;
ALTER TABLE topico.appointment_event ADD CONSTRAINT ck_appointment_event_action CHECK (action IN (
    'REGISTER', 'ACTIVATE', 'CALL', 'REQUEUE', 'START', 'FINISH', 'CANCEL', 'NO_SHOW', 'VOID', 'MIGRATE',
    'CLOSE_DAY', 'PRIORITY'));
