-- Reversión de la revisión 0002 (solo desarrollo/pruebas).
SET search_path TO topico, public;

DELETE FROM topico.system_parameter;
DELETE FROM topico.notification_template;
DELETE FROM topico.reason;
DELETE FROM topico.site_schedule;

-- La guarda impide borrar configuraciones vigentes; se deshabilita solo durante la reversión.
ALTER TABLE topico.site_setting_version DISABLE TRIGGER trg_site_setting_version_guard;
DELETE FROM topico.site_setting_version;
ALTER TABLE topico.site_setting_version ENABLE TRIGGER trg_site_setting_version_guard;

DELETE FROM topico.site;
DELETE FROM topico.insurer;
DELETE FROM topico.role_permission;
DELETE FROM topico.role;
DELETE FROM topico.permission;
DELETE FROM topico.appointment_status_transition;
DELETE FROM topico.appointment_status;
