-- Reversión de la revisión 0015.
SET search_path TO topico, public;

DROP TRIGGER trg_appointment_one_attention_per_day ON topico.appointment;
DROP FUNCTION topico.trg_appointment_one_attention_per_day();
