-- Reversión de la revisión 0003.
SET search_path TO topico, public;

DELETE FROM topico.system_parameter WHERE key LIKE 'display.%';
