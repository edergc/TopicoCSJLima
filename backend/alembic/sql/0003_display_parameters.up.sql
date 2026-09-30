-- Revisión 0003: parámetros de la pantalla pública de turnos (sala de espera / TV).
SET search_path TO topico, public;

INSERT INTO topico.system_parameter (key, value, value_type, description, is_editable) VALUES
    ('display.enabled',       'true'::jsonb, 'bool',   'Habilita la pantalla pública de turnos (/pantalla) para la sala de espera.', true),
    ('display.show_names',    'true'::jsonb, 'bool',   'Muestra en la pantalla el nombre abreviado (p. ej. "María G."); si se desactiva, solo el código de turno.', true),
    ('display.voice_enabled', 'true'::jsonb, 'bool',   'Anuncia por voz el turno llamado en la pantalla pública.', true),
    ('display.message',       '"Por favor, permanezca atento al llamado. Tenga a la mano su DNI."'::jsonb, 'string', 'Mensaje informativo que se muestra al pie de la pantalla de turnos.', true);
