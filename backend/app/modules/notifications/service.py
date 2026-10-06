"""Encolado de notificaciones (patrón outbox).

El dominio solo inserta filas `notification` dentro de SU transacción: si la operación se
revierte, no sale ningún correo. El envío real lo hace el dispatcher (worker.py).
El contenido se renderiza al encolar, de modo que queda constancia exacta de lo enviado.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.logging import get_logger
from app.modules.admin.parameters import get_int, get_str
from app.modules.appointments.models import Appointment
from app.modules.branding import service as branding
from app.modules.notifications.models import Notification, NotificationTemplate
from app.modules.notifications.templating import render

log = get_logger(__name__)

REGISTERED = "APPT_REGISTERED"
UPCOMING = "APPT_UPCOMING"
CALLED = "APPT_CALLED"
CANCELLED = "APPT_CANCELLED"


def build_context(
    db: Session,
    appointment: Appointment,
    clock: Clock,
    settings: Settings,
    *,
    people_ahead: int | None = None,
    estimated_time: datetime | None = None,
    reason_label: str | None = None,
) -> dict[str, Any]:
    tz = clock.tz
    return {
        "worker_first_name": appointment.worker.first_names.split()[0].title(),
        "ticket_code": appointment.ticket_code,
        "site_name": appointment.site.name,
        "room_name": appointment.room.name if appointment.room else "",
        "location_note": ", ".join(
            part
            for part in (
                appointment.room.name if appointment.room else None,
                appointment.room.location_note if appointment.room else None,
                appointment.site.location_note,
            )
            if part
        ),
        "service_date": f"{appointment.service_date:%d/%m/%Y}",
        "registered_time": f"{appointment.registered_at.astimezone(tz):%H:%M}",
        "people_ahead": people_ahead if people_ahead is not None else "",
        "estimated_time": f"{estimated_time.astimezone(tz):%H:%M}" if estimated_time else "",
        "reason_label": reason_label or "",
        "institution_name": get_str(db, "institution.name", "Corte Superior de Justicia de Lima"),
        "public_status_url": settings.public_app_url or "",
    }


def enqueue(
    db: Session,
    *,
    template_code: str,
    appointment: Appointment,
    context: dict[str, Any],
    now: datetime,
    notifications_enabled: bool,
    created_by: int | None,
    dedup_key: str | None = None,
) -> None:
    template = db.scalar(
        select(NotificationTemplate).where(
            NotificationTemplate.code == template_code, NotificationTemplate.channel == "EMAIL"
        )
    )
    if template is None or not template.is_active:
        return

    recipient = appointment.worker.institutional_email
    status = "PENDING"
    last_error = None
    if not notifications_enabled:
        status, last_error = "SKIPPED", "Notificaciones desactivadas para la sede."
    elif not recipient:
        status, last_error = "SKIPPED", "El trabajador no tiene correo registrado."

    try:
        subject = render(template.subject, context)[:200]
        body_text = render(template.body_text, context)
        body_html = render(template.body_html, context) if template.body_html else None
        if body_html is None and body_text:
            body_html = branding.email_html(body_text, branding.get_branding(db))
    except Exception as exc:  # una plantilla defectuosa no debe impedir la operación
        log.error("notification_render_failed", template=template_code, error=str(exc))
        subject, body_text, body_html = template.subject, None, None
        status, last_error = "FAILED", f"Error al renderizar la plantilla: {exc}"[:1000]

    values = {
        "appointment_id": appointment.id,
        "template_code": template_code,
        "channel": "EMAIL",
        "recipient": recipient if status != "SKIPPED" else None,
        "subject": subject,
        "body_text": body_text,
        "body_html": body_html,
        "status": status,
        "max_attempts": get_int(db, "notification.max_attempts", 5),
        "next_attempt_at": now,
        "last_error": last_error,
        "dedup_key": dedup_key,
        "created_by": created_by,
    }
    # ON CONFLICT DO NOTHING: una notificación deduplicada nunca rompe la transacción del caso de uso.
    db.execute(insert(Notification).values(**values).on_conflict_do_nothing(index_elements=["dedup_key"]))


def enqueue_direct(
    db: Session,
    *,
    template_code: str,
    recipient: str,
    context: dict[str, Any],
    now: datetime,
    created_by: int | None,
    dedup_key: str | None = None,
    attachment: tuple[str, str, bytes] | None = None,
) -> bool:
    """Correo a un destinatario interno (no ligado a una atención), p. ej. el resumen del día. False si no se encola."""
    template = db.scalar(
        select(NotificationTemplate).where(
            NotificationTemplate.code == template_code, NotificationTemplate.channel == "EMAIL"
        )
    )
    if template is None or not template.is_active:
        return False
    try:
        subject = render(template.subject, context)[:200]
        body_text = render(template.body_text, context)
        body_html = render(template.body_html, context) if template.body_html else None
        if body_html is None and body_text:
            body_html = branding.email_html(body_text, branding.get_branding(db))
    except Exception as exc:
        log.error("notification_render_failed", template=template_code, error=str(exc))
        return False
    name, mime, data = attachment if attachment else (None, None, None)
    db.execute(
        insert(Notification)
        .values(
            appointment_id=None,
            template_code=template_code,
            channel="EMAIL",
            recipient=recipient,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            status="PENDING",
            max_attempts=get_int(db, "notification.max_attempts", 5),
            next_attempt_at=now,
            dedup_key=dedup_key,
            created_by=created_by,
            attachment_name=name,
            attachment_type=mime,
            attachment_data=data,
        )
        .on_conflict_do_nothing(index_elements=["dedup_key"])
    )
    return True
