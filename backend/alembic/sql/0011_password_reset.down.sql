-- Reversión de la revisión 0011.
SET search_path TO topico, public;

DELETE FROM topico.notification_template WHERE code = 'PASSWORD_RESET';
DELETE FROM topico.system_parameter WHERE key = 'auth.password_reset_minutes';
DROP TABLE topico.password_reset;
