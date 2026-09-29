-- =============================================================================
--  Tópico CSJ Lima — Datos de referencia (revisión 0002)
--
--  Contiene catálogos que forman parte del diseño (estados, transiciones, permisos,
--  roles base) y valores INICIALES de configuración institucional (sedes, capacidad,
--  horarios, motivos, plantillas), editables luego desde el módulo de Administración.
--
--  NO crea usuarios: el primer administrador se crea con el comando de la CLI del backend
--  (así no existen contraseñas por defecto).
-- =============================================================================

SET search_path TO topico, public;

-- ---------------------------------------------------------------------------
-- Estados de la atención
-- ---------------------------------------------------------------------------
INSERT INTO topico.appointment_status
    (code, label, description, consumes_capacity, is_final, is_active_queue, sort_order) VALUES
    ('REGISTRADO',    'Registrado',    'Solicitud registrada para una fecha futura.',                   true,  false, true,  10),
    ('EN_ESPERA',     'En espera',     'En la cola del día, esperando ser llamado.',                    true,  false, true,  20),
    ('LLAMADO',       'Llamado',       'Se llamó al trabajador para que acuda al tópico.',              true,  false, true,  30),
    ('EN_ATENCION',   'En atención',   'El trabajador está siendo atendido.',                           true,  false, true,  40),
    ('ATENDIDO',      'Atendido',      'La atención concluyó.',                                         true,  true,  false, 50),
    ('CANCELADO',     'Cancelado',     'El trabajador desistió de la atención. Libera el cupo.',        false, true,  false, 60),
    ('NO_PRESENTADO', 'No presentado', 'No acudió tras ser llamado y vencer la tolerancia. Libera el cupo.', false, true, false, 70),
    ('ANULADO',       'Anulado',       'Registro anulado por error administrativo. Libera el cupo.',   false, true,  false, 80);

-- ---------------------------------------------------------------------------
-- Máquina de estados (únicas transiciones permitidas)
-- ---------------------------------------------------------------------------
INSERT INTO topico.appointment_status_transition (from_status, to_status, action) VALUES
    ('REGISTRADO',  'EN_ESPERA',     'ACTIVATE'),
    ('REGISTRADO',  'CANCELADO',     'CANCEL'),
    ('REGISTRADO',  'ANULADO',       'VOID'),
    ('EN_ESPERA',   'LLAMADO',       'CALL'),
    ('EN_ESPERA',   'CANCELADO',     'CANCEL'),
    ('EN_ESPERA',   'ANULADO',       'VOID'),
    ('LLAMADO',     'EN_ATENCION',   'START'),
    ('LLAMADO',     'EN_ESPERA',     'REQUEUE'),
    ('LLAMADO',     'NO_PRESENTADO', 'NO_SHOW'),
    ('LLAMADO',     'CANCELADO',     'CANCEL'),
    ('EN_ATENCION', 'ATENDIDO',      'FINISH');

-- ---------------------------------------------------------------------------
-- Permisos
-- ---------------------------------------------------------------------------
INSERT INTO topico.permission (code, module, description) VALUES
    ('user:read',              'users',         'Ver usuarios'),
    ('user:manage',            'users',         'Crear, modificar, desactivar usuarios y asignar roles/sedes'),
    ('role:read',              'users',         'Ver roles y permisos'),
    ('role:manage',            'users',         'Crear y modificar roles y sus permisos'),
    ('worker:lookup',          'workers',       'Buscar trabajador por documento y verificar habilitación'),
    ('worker:read',            'workers',       'Ver ficha y listado de trabajadores'),
    ('worker:manage',          'workers',       'Crear/modificar trabajadores y coberturas EPS'),
    ('import:manage',          'imports',       'Cargar, validar y confirmar importaciones de Excel'),
    ('site:read',              'sites',         'Ver sedes, disponibilidad y horarios'),
    ('site:configure',         'sites',         'Configurar capacidad, horarios, tolerancia y cierres de sede'),
    ('service_day:adjust',     'agenda',        'Ajustar la capacidad del día en curso (auditado)'),
    ('service_day:close',      'agenda',        'Cerrar el día operativo'),
    ('queue:read',             'queue',         'Ver la cola y el panel operativo'),
    ('appointment:read',       'appointments',  'Ver atenciones y su historial'),
    ('appointment:create',     'appointments',  'Registrar atenciones'),
    ('appointment:operate',    'appointments',  'Llamar, iniciar, finalizar y devolver a la cola'),
    ('appointment:cancel',     'appointments',  'Cancelar atenciones'),
    ('appointment:no_show',    'appointments',  'Marcar no presentado'),
    ('appointment:void',       'appointments',  'Anular atenciones por error de registro'),
    ('notification:read',      'notifications', 'Ver el estado de las notificaciones'),
    ('notification:resend',    'notifications', 'Reenviar notificaciones'),
    ('report:read',            'reports',       'Ver reportes agregados'),
    ('report:read_nominal',    'reports',       'Ver reportes con datos personales (nominales)'),
    ('report:export',          'reports',       'Exportar reportes (Excel/CSV)'),
    ('audit:read',             'audit',         'Consultar la auditoría'),
    ('audit:verify',           'audit',         'Verificar la integridad de la cadena de auditoría'),
    ('catalog:manage',         'admin',         'Administrar motivos y catálogos'),
    ('template:manage',        'admin',         'Administrar plantillas de notificación'),
    ('parameter:manage',       'admin',         'Administrar parámetros del sistema');

-- ---------------------------------------------------------------------------
-- Roles base
-- ---------------------------------------------------------------------------
INSERT INTO topico.role (code, name, description, is_system) VALUES
    ('ADMIN',      'Administrador del sistema', 'Usuarios, roles, parámetros, catálogos e importaciones. No opera la cola.', true),
    ('SUPERVISOR', 'Supervisor(a)',             'Supervisa ambas sedes (según asignación), configura la sede, reportes y exportaciones.', true),
    ('OPERATOR',   'Encargado(a) del tópico',   'Opera la mesa de atención de su(s) sede(s) asignada(s).', true),
    ('AUDITOR',    'Auditor(a)',                'Solo lectura de auditoría y reportes agregados.', true);

INSERT INTO topico.role_permission (role_id, permission_id)
SELECT r.id, p.id
  FROM (VALUES
    ('ADMIN', 'user:read'), ('ADMIN', 'user:manage'), ('ADMIN', 'role:read'), ('ADMIN', 'role:manage'),
    ('ADMIN', 'worker:lookup'), ('ADMIN', 'worker:read'), ('ADMIN', 'worker:manage'), ('ADMIN', 'import:manage'),
    ('ADMIN', 'site:read'), ('ADMIN', 'site:configure'), ('ADMIN', 'queue:read'), ('ADMIN', 'appointment:read'),
    ('ADMIN', 'notification:read'), ('ADMIN', 'report:read'), ('ADMIN', 'audit:read'), ('ADMIN', 'audit:verify'),
    ('ADMIN', 'catalog:manage'), ('ADMIN', 'template:manage'), ('ADMIN', 'parameter:manage'),

    ('SUPERVISOR', 'worker:lookup'), ('SUPERVISOR', 'worker:read'), ('SUPERVISOR', 'site:read'),
    ('SUPERVISOR', 'site:configure'), ('SUPERVISOR', 'service_day:adjust'), ('SUPERVISOR', 'service_day:close'),
    ('SUPERVISOR', 'queue:read'), ('SUPERVISOR', 'appointment:read'), ('SUPERVISOR', 'appointment:create'),
    ('SUPERVISOR', 'appointment:operate'), ('SUPERVISOR', 'appointment:cancel'), ('SUPERVISOR', 'appointment:no_show'),
    ('SUPERVISOR', 'appointment:void'), ('SUPERVISOR', 'notification:read'), ('SUPERVISOR', 'notification:resend'),
    ('SUPERVISOR', 'report:read'), ('SUPERVISOR', 'report:read_nominal'), ('SUPERVISOR', 'report:export'),

    ('OPERATOR', 'worker:lookup'), ('OPERATOR', 'site:read'), ('OPERATOR', 'queue:read'),
    ('OPERATOR', 'appointment:read'), ('OPERATOR', 'appointment:create'), ('OPERATOR', 'appointment:operate'),
    ('OPERATOR', 'appointment:cancel'), ('OPERATOR', 'appointment:no_show'), ('OPERATOR', 'appointment:void'),
    ('OPERATOR', 'notification:read'), ('OPERATOR', 'notification:resend'), ('OPERATOR', 'report:read'),

    ('AUDITOR', 'user:read'), ('AUDITOR', 'role:read'), ('AUDITOR', 'site:read'), ('AUDITOR', 'appointment:read'),
    ('AUDITOR', 'report:read'), ('AUDITOR', 'audit:read'), ('AUDITOR', 'audit:verify')
  ) AS m(role_code, permission_code)
  JOIN topico.role r       ON r.code = m.role_code
  JOIN topico.permission p ON p.code = m.permission_code;

-- ---------------------------------------------------------------------------
-- EPS
-- ---------------------------------------------------------------------------
INSERT INTO topico.insurer (code, name) VALUES ('RIMAC', 'EPS Rímac');

-- ---------------------------------------------------------------------------
-- Sedes y configuración inicial
--   Valores de referencia tomados del requerimiento (capacidad 20, turnos de 15 min,
--   mañana 08:00–12:00, tarde 14:00–17:00). Tolerancia de 10 min: SUPUESTO a confirmar.
--   La sede Anselmo Barreto se inicializa igual; debe ajustarse desde Administración.
-- ---------------------------------------------------------------------------
INSERT INTO topico.site (code, name, short_name, ticket_prefix) VALUES
    ('ALZ', 'Sede Javier Alzamora Valdez', 'Alzamora Valdez', 'A'),
    ('BAR', 'Sede Anselmo Barreto',        'Anselmo Barreto', 'B');

INSERT INTO topico.site_setting_version
    (site_id, valid_from, daily_capacity, slot_minutes, tolerance_minutes, max_concurrent_in_service,
     registration_cutoff_minutes, upcoming_notice_ahead, allow_reregister_after_no_show,
     allow_reregister_after_cancel, notifications_enabled, change_reason)
SELECT s.id, DATE '2026-01-01', 20, 15, 10, 1, 0, 2, false, true, true,
       'Configuración inicial (valores de referencia del requerimiento; confirmar con el área usuaria)'
  FROM topico.site s;

INSERT INTO topico.site_schedule (site_id, weekday, block, start_time, end_time, valid_from)
SELECT s.id, d.weekday, b.block, b.start_time, b.end_time, DATE '2026-01-01'
  FROM topico.site s
 CROSS JOIN generate_series(1, 5) AS d(weekday)
 CROSS JOIN (VALUES ('AM', TIME '08:00', TIME '12:00'),
                    ('PM', TIME '14:00', TIME '17:00')) AS b(block, start_time, end_time);

-- ---------------------------------------------------------------------------
-- Motivos administrativos
-- ---------------------------------------------------------------------------
INSERT INTO topico.reason (type, code, label, requires_note, sort_order) VALUES
    ('CANCEL',  'ATENCION_EXTERNA',       'Se atenderá en una clínica u otro establecimiento', false, 10),
    ('CANCEL',  'YA_NO_REQUIERE',         'Ya no requiere la atención',                         false, 20),
    ('CANCEL',  'MOTIVOS_LABORALES',      'Motivos laborales / no puede ausentarse',            false, 30),
    ('CANCEL',  'REPROGRAMACION',         'Reprogramación a otra fecha',                        false, 40),
    ('CANCEL',  'OTRO',                   'Otro motivo',                                        true,  99),
    ('VOID',    'TRABAJADOR_EQUIVOCADO',  'Se registró a otro trabajador por error',            false, 10),
    ('VOID',    'REGISTRO_DUPLICADO',     'Registro duplicado',                                 false, 20),
    ('VOID',    'SEDE_EQUIVOCADA',        'Se registró en la sede equivocada',                  false, 30),
    ('VOID',    'OTRO',                   'Otro error de registro',                             true,  99),
    ('NO_SHOW', 'NO_ACUDIO',              'No acudió tras ser llamado',                         false, 10),
    ('NO_SHOW', 'NO_UBICADO',             'No se le pudo ubicar',                               false, 20),
    ('REQUEUE', 'NO_DISPONIBLE_MOMENTO',  'No disponible en este momento; se atenderá luego',   false, 10),
    ('REQUEUE', 'OTRO',                   'Otro motivo',                                        true,  99);

-- ---------------------------------------------------------------------------
-- Plantillas de correo (Jinja2 en sandbox). Variables disponibles:
--   worker_first_name, ticket_code, site_name, location_note, service_date,
--   registered_time, people_ahead, estimated_time, reason_label, institution_name
-- ---------------------------------------------------------------------------
INSERT INTO topico.notification_template (code, channel, description, subject, body_text) VALUES
('APPT_REGISTERED', 'EMAIL', 'Confirmación de registro de la solicitud de atención',
 'Tópico de Salud: su turno {{ ticket_code }} ha sido registrado',
 'Estimado(a) {{ worker_first_name }}:

Su solicitud de atención en el Tópico de Salud ha sido registrada.

  Turno:           {{ ticket_code }}
  Sede:            {{ site_name }}
  Fecha:           {{ service_date }}
  Hora de registro: {{ registered_time }}
{% if estimated_time %}  Hora estimada:   {{ estimated_time }} (referencial)
{% endif %}
Le avisaremos cuando su atención se aproxime. Si ya no requiere la atención, comuníquese con el tópico para liberar el cupo.

{{ institution_name }}
Este es un mensaje automático; por favor no responda a este correo.'),

('APPT_UPCOMING', 'EMAIL', 'Aviso de proximidad del turno',
 'Tópico de Salud: su atención se aproxima (turno {{ ticket_code }})',
 'Estimado(a) {{ worker_first_name }}:

Su atención se aproxima. Actualmente hay {{ people_ahead }} persona(s) delante de usted.

  Turno: {{ ticket_code }}
  Sede:  {{ site_name }}

Por favor, manténgase atento(a) al llamado.

{{ institution_name }}
Este es un mensaje automático; por favor no responda a este correo.'),

('APPT_CALLED', 'EMAIL', 'Llamado al trabajador',
 'Tópico de Salud: por favor acérquese al tópico (turno {{ ticket_code }})',
 'Estimado(a) {{ worker_first_name }}:

Es su turno. Por favor, acérquese al Tópico de Salud.

  Turno: {{ ticket_code }}
  Sede:  {{ site_name }}
{% if location_note %}  Ubicación: {{ location_note }}
{% endif %}
{{ institution_name }}
Este es un mensaje automático; por favor no responda a este correo.'),

('APPT_CANCELLED', 'EMAIL', 'Confirmación de cancelación',
 'Tópico de Salud: su solicitud {{ ticket_code }} ha sido cancelada',
 'Estimado(a) {{ worker_first_name }}:

Su solicitud de atención ha sido cancelada.

  Turno:  {{ ticket_code }}
  Sede:   {{ site_name }}
  Fecha:  {{ service_date }}
{% if reason_label %}  Motivo: {{ reason_label }}
{% endif %}
Si necesita una nueva atención, comuníquese con el tópico.

{{ institution_name }}
Este es un mensaje automático; por favor no responda a este correo.');

-- ---------------------------------------------------------------------------
-- Parámetros globales
-- ---------------------------------------------------------------------------
INSERT INTO topico.system_parameter (key, value, value_type, description, is_editable) VALUES
    ('app.timezone',                 '"America/Lima"'::jsonb, 'string', 'Zona horaria institucional para fechas operativas.', false),
    ('institution.name',             '"Corte Superior de Justicia de Lima"'::jsonb, 'string', 'Nombre de la institución (correos y reportes).', true),
    ('institution.system_name',      '"Sistema de Gestión del Tópico de Salud"'::jsonb, 'string', 'Nombre del sistema mostrado en la interfaz.', true),
    ('booking.advance_days_max',     '0'::jsonb,   'int',  'Días de anticipación permitidos para registrar (0 = solo el mismo día).', true),
    ('auth.max_failed_attempts',     '5'::jsonb,   'int',  'Intentos fallidos consecutivos antes del bloqueo temporal.', true),
    ('auth.lockout_minutes',         '15'::jsonb,  'int',  'Minutos de bloqueo tras superar los intentos fallidos.', true),
    ('auth.password_min_length',     '10'::jsonb,  'int',  'Longitud mínima de contraseña.', true),
    ('auth.refresh_token_hours',     '10'::jsonb,  'int',  'Duración máxima de una sesión (horas) antes de volver a autenticarse.', true),
    ('public_status.enabled',        'true'::jsonb,'bool', 'Habilita la consulta pública del estado del turno.', true),
    ('notification.max_attempts',    '5'::jsonb,   'int',  'Reintentos máximos de envío de una notificación.', true),
    ('notification.retry_base_seconds','60'::jsonb,'int',  'Segundos base del reintento exponencial.', true),
    ('import.max_file_mb',           '10'::jsonb,  'int',  'Tamaño máximo del archivo Excel a importar (MB).', true);
