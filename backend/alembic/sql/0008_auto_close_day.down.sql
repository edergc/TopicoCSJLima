SET search_path TO topico, public;

-- Los cierres automáticos no tienen usuario: no se puede volver a exigirlo sin perder ese dato.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM topico.appointment WHERE status = 'NO_PRESENTADO' AND closed_by IS NULL) THEN
        RAISE EXCEPTION 'Hay atenciones cerradas automáticamente (closed_by vacío): no se puede revertir 0008.';
    END IF;
END $$;

ALTER TABLE topico.appointment DROP CONSTRAINT ck_appointment_closed_data;
ALTER TABLE topico.appointment ADD CONSTRAINT ck_appointment_closed_data CHECK (
    status NOT IN ('CANCELADO', 'NO_PRESENTADO', 'ANULADO')
    OR (closed_at IS NOT NULL AND closed_by IS NOT NULL
        AND (close_reason_id IS NOT NULL OR channel = 'MIGRATION')));
