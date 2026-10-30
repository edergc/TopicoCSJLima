-- Revisión 0013: reporte de satisfacción para la jefatura y cierre de sesión por inactividad.
--   * Permiso rating:read: ver todos los comentarios anónimos de los trabajadores y exportarlos.
--     Lo tienen el Supervisor(a) (jefatura de las encargadas / Bienestar), el Administrador y el Auditor.
--     La Encargada del tópico sigue viendo solo los promedios en Reportes, no los comentarios.
--   * Parámetro auth.idle_timeout_minutes: minutos sin uso antes de cerrar la sesión (0 = desactivado).
SET search_path TO topico, public;

INSERT INTO topico.permission (code, module, description) VALUES
    ('rating:read', 'reports', 'Ver el reporte de satisfacción con todos los comentarios anónimos');

INSERT INTO topico.role_permission (role_id, permission_id)
SELECT r.id, p.id
  FROM topico.role r
  JOIN topico.permission p ON p.code = 'rating:read'
 WHERE r.code IN ('ADMIN', 'SUPERVISOR', 'AUDITOR');

UPDATE topico.role
   SET description = 'Jefatura de las encargadas (Bienestar): supervisa las sedes asignadas, ajusta y cierra el día, reportes y satisfacción del servicio.'
 WHERE code = 'SUPERVISOR';

INSERT INTO topico.system_parameter (key, value, value_type, description, is_editable) VALUES
    ('auth.idle_timeout_minutes', '20'::jsonb, 'int', 'Minutos sin uso tras los cuales se cierra la sesión (aviso 1 minuto antes; 0 = no cerrar por inactividad).', true);
