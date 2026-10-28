-- Revisión 0011: recuperación de contraseña por correo.
--   El usuario pide un enlace desde la pantalla de ingreso; el enlace caduca y sirve una sola vez.
--   Solo se guarda el SHA-256 del enlace (igual que las sesiones y las calificaciones).
SET search_path TO topico, public;

CREATE TABLE topico.password_reset (
    id            bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id       bigint       NOT NULL REFERENCES topico.app_user (id),
    token_hash    char(64)     NOT NULL,
    requested_at  timestamptz  NOT NULL DEFAULT now(),
    expires_at    timestamptz  NOT NULL,
    used_at       timestamptz,
    ip            inet,
    CONSTRAINT uq_password_reset_token UNIQUE (token_hash),
    CONSTRAINT ck_password_reset_hash_format CHECK (token_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_password_reset_expiry CHECK (expires_at > requested_at)
);
CREATE INDEX ix_password_reset_user ON topico.password_reset (user_id) WHERE used_at IS NULL;
COMMENT ON TABLE  topico.password_reset IS 'Enlaces de recuperación de contraseña (un solo uso, con vencimiento). Solo se guarda el SHA-256.';
COMMENT ON COLUMN topico.password_reset.used_at IS 'Momento en que se usó o se invalidó (al pedir otro enlace o al cambiar la contraseña).';

GRANT SELECT ON topico.password_reset TO topico_app, topico_readonly;
GRANT INSERT ON topico.password_reset TO topico_app;
GRANT UPDATE (used_at) ON topico.password_reset TO topico_app;

INSERT INTO topico.system_parameter (key, value, value_type, description, is_editable) VALUES
    ('auth.password_reset_minutes', '30'::jsonb, 'int', 'Minutos de validez del enlace de recuperación de contraseña enviado por correo.', true);

INSERT INTO topico.notification_template (code, channel, description, subject, body_text) VALUES
('PASSWORD_RESET', 'EMAIL', 'Enlace para restablecer la contraseña (solicitado desde la pantalla de ingreso)',
 'Tópico de Salud: restablecer su contraseña',
 'Estimado(a) {{ full_name }}:

Recibimos una solicitud para restablecer la contraseña del usuario «{{ username }}».
Para definir una nueva contraseña, abra este enlace:

  {{ reset_url }}

El enlace vence en {{ valid_minutes }} minutos y sirve una sola vez.
Si usted no lo solicitó, ignore este correo: su contraseña actual sigue vigente.

{{ institution_name }}
Este es un mensaje automático; por favor no responda a este correo.');
