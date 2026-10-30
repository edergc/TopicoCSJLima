-- Reversión de la revisión 0013.
SET search_path TO topico, public;

DELETE FROM topico.system_parameter WHERE key = 'auth.idle_timeout_minutes';
DELETE FROM topico.role_permission WHERE permission_id = (SELECT id FROM topico.permission WHERE code = 'rating:read');
DELETE FROM topico.permission WHERE code = 'rating:read';
UPDATE topico.role SET description = 'Supervisa ambas sedes (según asignación), configura la sede, reportes y exportaciones.' WHERE code = 'SUPERVISOR';
