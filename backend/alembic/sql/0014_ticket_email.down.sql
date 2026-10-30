-- Reversión de la revisión 0014 (texto original de la plantilla de registro).
SET search_path TO topico, public;

UPDATE topico.notification_template
   SET body_text = $tpl$Estimado(a) {{ worker_first_name }}:

Su solicitud de atención en el Tópico de Salud ha sido registrada.

  Turno:           {{ ticket_code }}
  Sede:            {{ site_name }}
  Fecha:           {{ service_date }}
  Hora de registro: {{ registered_time }}
{% if estimated_time %}  Hora estimada:   {{ estimated_time }} (referencial)
{% endif %}
Le avisaremos cuando su atención se aproxime. Si ya no requiere la atención, comuníquese con el tópico para liberar el cupo.

{{ institution_name }}
Este es un mensaje automático; por favor no responda a este correo.$tpl$
 WHERE code = 'APPT_REGISTERED' AND body_text LIKE '%status_link%';
