-- Revisión 0014: correo de registro como ticket digital.
--   El correo HTML (ticket con botón y PDF adjunto con QR) se arma en el código; esta plantilla
--   da el saludo y la versión de texto plano. Solo se reemplaza si el administrador no la modificó.
SET search_path TO topico, public;

UPDATE topico.notification_template
   SET body_text = $tpl$Estimado(a) {{ worker_first_name }}:

Su solicitud de atención en el Tópico de Salud ha sido registrada. Este es su turno:

  Turno:            {{ ticket_code }}
  Sede:             {{ site_name }}
  Fecha:            {{ service_date }}
  Hora de registro: {{ registered_time }}
{% if people_ahead != "" %}  Personas delante: {{ people_ahead }}
{% endif %}{% if estimated_time %}  Hora estimada:    {{ estimated_time }} (referencial)
{% endif %}
{% if status_link %}Siga su turno en tiempo real: {{ status_link }}

{% endif %}Diríjase a la sala de espera y esté atento a la pantalla y al llamado de su turno. Le avisaremos cuando su atención se aproxime. Si ya no requiere la atención, comuníquese con el tópico para liberar el cupo.

Este es un mensaje automático; por favor no responda a este correo.$tpl$
 WHERE code = 'APPT_REGISTERED'
   AND body_text LIKE 'Estimado(a) {{ worker_first_name }}:%Le avisaremos cuando su atención se aproxime.%'
   AND body_text NOT LIKE '%status_link%';
