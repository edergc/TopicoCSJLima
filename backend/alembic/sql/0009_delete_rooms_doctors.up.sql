-- Revisión 0009: consultorios y médicos se pueden eliminar si nunca se usaron en una atención.
--   La aplicación lo verifica antes; las claves foráneas de appointment y service_rating impiden,
--   además, borrar uno con historial (en ese caso se desactiva).
SET search_path TO topico, public;

GRANT DELETE ON topico.consulting_room, topico.doctor TO topico_app;
