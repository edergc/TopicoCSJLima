from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.core.errors import BusinessRuleError, NotFoundError
from app.modules.appointments.models import Appointment
from app.modules.appointments.router import notification_out
from app.modules.appointments.schemas import NotificationOut
from app.modules.auth.dependencies import ServiceContext, require
from app.modules.notifications.models import Notification
from app.shared.schemas import Page, PageParams

router = APIRouter(prefix="/notifications", tags=["Notificaciones"])


@router.get("", response_model=Page[NotificationOut], summary="Bandeja de notificaciones (sedes autorizadas)")
def list_notifications(
    ctx: Annotated[ServiceContext, Depends(require("notification:read"))],
    paging: Annotated[PageParams, Depends()],
    status: Annotated[str | None, Query(max_length=10)] = None,
    site_id: int | None = None,
) -> Page[NotificationOut]:
    site_ids = sorted(ctx.user.site_ids)
    if site_id is not None:
        ctx.require_site(site_id, action="NOTIFICATION_LIST")
        site_ids = [site_id]
    stmt = select(Notification).join(Appointment, Appointment.id == Notification.appointment_id)
    stmt = stmt.where(Appointment.site_id.in_(site_ids))
    if status:
        stmt = stmt.where(Notification.status == status)
    total = ctx.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = ctx.db.scalars(stmt.order_by(Notification.id.desc()).offset(paging.offset).limit(paging.size))
    return Page(items=[notification_out(n) for n in rows], total=total, page=paging.page, size=paging.size)


@router.post("/{notification_id}/resend", response_model=NotificationOut, status_code=201, summary="Reenviar")
def resend(
    notification_id: int, ctx: Annotated[ServiceContext, Depends(require("notification:resend"))]
) -> NotificationOut:
    original = ctx.db.get(Notification, notification_id)
    if original is None or original.appointment_id is None:
        raise NotFoundError()
    appointment = ctx.db.get(Appointment, original.appointment_id)
    assert appointment is not None
    ctx.require_site(appointment.site_id, action="NOTIFICATION_RESEND")
    recipient = appointment.worker.institutional_email
    if not recipient:
        raise BusinessRuleError("VALIDATION_ERROR", "El trabajador no tiene correo registrado.")
    copy = Notification(
        appointment_id=original.appointment_id,
        template_code=original.template_code,
        channel=original.channel,
        recipient=recipient,
        subject=original.subject,
        body_text=original.body_text,
        body_html=original.body_html,
        status="PENDING",
        attempts=0,
        max_attempts=original.max_attempts,
        next_attempt_at=ctx.clock.now(),
        created_by=ctx.user.id,
    )
    ctx.db.add(copy)
    ctx.db.flush()
    ctx.audit(
        action="NOTIFICATION_RESEND",
        resource_type="notification",
        resource_id=copy.id,
        site_id=appointment.site_id,
        metadata={"original_id": original.id, "template": original.template_code},
    )
    ctx.db.commit()
    ctx.db.refresh(copy)
    return notification_out(copy)
