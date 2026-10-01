-- Reversión de la revisión 0004.
SET search_path TO topico, public;

ALTER TABLE topico.appointment DROP COLUMN doctor_id;
DROP TABLE topico.doctor;
