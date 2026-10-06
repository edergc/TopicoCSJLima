-- Reversión de la revisión 0005.
SET search_path TO topico, public;

ALTER TABLE topico.appointment DROP COLUMN room_id;
DROP TABLE topico.consulting_room;

DELETE FROM topico.role_permission
 WHERE permission_id = (SELECT id FROM topico.permission WHERE code = 'site:manage');
DELETE FROM topico.permission WHERE code = 'site:manage';
