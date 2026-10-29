-- Reversión de la revisión 0012.
SET search_path TO topico, public;

ALTER TABLE topico.app_user DROP CONSTRAINT ck_app_user_username_format;
ALTER TABLE topico.app_user ADD CONSTRAINT ck_app_user_username_format CHECK (username ~ '^[a-z0-9][a-z0-9._-]{2,49}$');
COMMENT ON COLUMN topico.app_user.username IS 'Nombre de usuario en minúsculas.';
