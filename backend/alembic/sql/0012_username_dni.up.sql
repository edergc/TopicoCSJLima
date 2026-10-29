-- Revisión 0012: el usuario del sistema es el DNI de la persona (exactamente 8 dígitos 0-9, con ceros).
--   Antes se aplica, todo usuario que no sea un DNI debe renombrarse (conserva contraseña e historial):
--     python -m app.cli rename-user --from admin --to <DNI de 8 dígitos>
SET search_path TO topico, public;

DO $$
DECLARE
    v_bad text;
BEGIN
    SELECT string_agg(username, ', ' ORDER BY username) INTO v_bad
      FROM topico.app_user WHERE username !~ '^[0-9]{8}$';
    IF v_bad IS NOT NULL THEN
        RAISE EXCEPTION 'Usuarios que no son un DNI de 8 dígitos: %. Renómbrelos antes de migrar: python -m app.cli rename-user --from <usuario> --to <DNI>', v_bad;
    END IF;
END $$;

ALTER TABLE topico.app_user DROP CONSTRAINT ck_app_user_username_format;
ALTER TABLE topico.app_user ADD CONSTRAINT ck_app_user_username_format CHECK (username ~ '^[0-9]{8}$');
COMMENT ON COLUMN topico.app_user.username IS 'Usuario de ingreso = DNI de la persona (exactamente 8 dígitos, admite ceros a la izquierda y a la derecha).';
