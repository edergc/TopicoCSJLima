-- Revisión 0008: cierre automático de la jornada.
--   El sistema cierra los días pasados que quedaron abiertos: los pendientes pasan a NO_PRESENTADO
--   con el motivo «Cierre de jornada», sin una persona detrás (closed_by vacío; la auditoría lo
--   registra como «sistema»). Cancelar y anular siguen exigiendo al usuario que lo hizo.
SET search_path TO topico, public;

ALTER TABLE topico.appointment DROP CONSTRAINT ck_appointment_closed_data;
ALTER TABLE topico.appointment ADD CONSTRAINT ck_appointment_closed_data CHECK (
    status NOT IN ('CANCELADO', 'NO_PRESENTADO', 'ANULADO')
    OR (closed_at IS NOT NULL
        AND (closed_by IS NOT NULL OR status = 'NO_PRESENTADO')
        AND (close_reason_id IS NOT NULL OR channel = 'MIGRATION')));
