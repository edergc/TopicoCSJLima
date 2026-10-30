-- Revisión 0015: una sola atención por trabajador y día (en cualquier sede).
--   Ya existía uq_appointment_worker_active_day (no dos atenciones vivas a la vez). Faltaba impedir un
--   nuevo registro cuando el trabajador ya fue ATENDIDO ese día. El backend lo valida antes; este
--   disparador es la última línea de defensa. Los datos migrados (channel = MIGRATION) quedan fuera.
--   Solo actúa al insertar: no altera atenciones existentes.
SET search_path TO topico, public;

CREATE FUNCTION topico.trg_appointment_one_attention_per_day()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = topico, pg_temp
AS $$
DECLARE
    v_ticket varchar(12);
BEGIN
    IF NEW.channel = 'MIGRATION' THEN
        RETURN NEW;
    END IF;
    SELECT a.ticket_code INTO v_ticket
      FROM topico.appointment a
     WHERE a.worker_id = NEW.worker_id
       AND a.service_date = NEW.service_date
       AND a.status = 'ATENDIDO'
     LIMIT 1;
    IF FOUND THEN
        RAISE EXCEPTION 'El trabajador ya fue atendido el % (turno %): solo se permite una atención por día', NEW.service_date, v_ticket
            USING ERRCODE = 'check_violation', CONSTRAINT = 'ck_appointment_one_attention_per_day';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER trg_appointment_one_attention_per_day
    BEFORE INSERT ON topico.appointment
    FOR EACH ROW EXECUTE FUNCTION topico.trg_appointment_one_attention_per_day();

COMMENT ON FUNCTION topico.trg_appointment_one_attention_per_day() IS
    'Impide registrar una atención para un trabajador que ya fue ATENDIDO ese mismo día (en cualquier sede).';
