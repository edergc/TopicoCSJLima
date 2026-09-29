-- =============================================================================
--  Reversión de la revisión 0001. ¡DESTRUCTIVO! Elimina todas las tablas del sistema.
--  Solo para desarrollo/pruebas. En producción nunca se revierte la revisión base.
-- =============================================================================

SET search_path TO topico, public;

DROP TABLE IF EXISTS
    topico.audit_event,
    topico.notification,
    topico.notification_template,
    topico.appointment_event,
    topico.appointment,
    topico.service_day,
    topico.appointment_status_transition,
    topico.appointment_status,
    topico.reason,
    topico.import_row,
    topico.worker_coverage,
    topico.worker,
    topico.insurer,
    topico.department,
    topico.import_batch,
    topico.site_closure,
    topico.site_schedule,
    topico.site_setting_version,
    topico.system_parameter,
    topico.refresh_token,
    topico.user_site,
    topico.site,
    topico.user_role,
    topico.role_permission,
    topico.permission,
    topico.role,
    topico.app_user
CASCADE;

DROP FUNCTION IF EXISTS topico.verify_audit_chain();
DROP FUNCTION IF EXISTS topico.tg_audit_event_before_insert();
DROP FUNCTION IF EXISTS topico.tg_appointment_before_update();
DROP FUNCTION IF EXISTS topico.tg_appointment_before_insert();
DROP FUNCTION IF EXISTS topico.ensure_service_day(integer, date);
DROP FUNCTION IF EXISTS topico.tg_site_setting_version_guard();
DROP FUNCTION IF EXISTS topico.tg_forbid_change();
DROP FUNCTION IF EXISTS topico.tg_set_updated_at();
DROP TYPE IF EXISTS topico.timerange;
