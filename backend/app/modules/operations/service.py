"""Operación del tópico: pausa (2.3), cierre del día (2.4), panel en vivo (2.5) y mensajes de sala (2.7)."""

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.context import get_request_context
from app.core.errors import BusinessRuleError, NotFoundError
from app.modules.admin.parameters import get_bool
from app.modules.appointments import queue as queue_view
from app.modules.appointments.models import Appointment, AppointmentEvent, Reason
from app.modules.appointments.state_machine import Status
from app.modules.auth.dependencies import ServiceContext
from app.modules.branding import service as branding
from app.modules.notifications import service as notifications
from app.modules.reports import documents
from app.modules.reports import service as reports
from app.modules.sites import service as sites
from app.modules.sites.models import DisplayMessage, Site, SitePause
from app.modules.users.models import AppUser, Role, user_role, user_site

# ================================================================== pausa (2.3)


def active_pause(db: Session, site_id: int) -> SitePause | None:
    return db.scalar(select(SitePause).where(SitePause.site_id == site_id, SitePause.ended_at.is_(None)))


def end_pause(db: Session, pause: SitePause, now: datetime, user_id: int | None) -> None:
    pause.ended_at = max(now, pause.started_at)
    pause.ended_by = user_id


def pause_site(ctx: ServiceContext, site_id: int, reason: str, minutes: int) -> SitePause:
    ctx.require_site(site_id, action="SITE_PAUSE")
    sites.get_site(ctx.db, site_id, active_only=True)
    if active_pause(ctx.db, site_id) is not None:
        raise BusinessRuleError("SITE_ALREADY_PAUSED")
    now = ctx.clock.now()
    pause = SitePause(
        site_id=site_id,
        started_at=now,
        resume_at=now + timedelta(minutes=minutes),
        reason=reason,
        created_by=ctx.user.id,
    )
    ctx.db.add(pause)
    ctx.db.flush()
    ctx.audit(
        action="SITE_PAUSE",
        resource_type="site",
        resource_id=site_id,
        site_id=site_id,
        reason=reason,
        after={"resume_at": pause.resume_at, "minutes": minutes},
    )
    ctx.db.commit()
    return pause


def resume_site(ctx: ServiceContext, site_id: int, *, automatic: bool = False) -> None:
    ctx.require_site(site_id, action="SITE_RESUME")
    pause = active_pause(ctx.db, site_id)
    if pause is None:
        if automatic:
            return
        raise BusinessRuleError("SITE_NOT_PAUSED")
    end_pause(ctx.db, pause, ctx.clock.now(), ctx.user.id)
    ctx.audit(
        action="SITE_RESUME",
        resource_type="site",
        resource_id=site_id,
        site_id=site_id,
        after={
            "automatic": automatic,
            "paused_minutes": int((ctx.clock.now() - pause.started_at).total_seconds() // 60),
        },
    )
    if not automatic:
        ctx.db.commit()


# ================================================================== cierre del día (2.4)

_PENDING = (Status.REGISTRADO, Status.EN_ESPERA, Status.LLAMADO)


def close_day(ctx: ServiceContext, site_id: int, day: date) -> dict[str, Any]:
    """Cierra la jornada: pendientes → NO_PRESENTADO (motivo automático), día CLOSED, resumen PDF por correo."""
    db, clock = ctx.db, ctx.clock
    ctx.require_site(site_id, action="SERVICE_DAY_CLOSE")
    site = sites.get_site(db, site_id)
    if day > clock.today():
        raise BusinessRuleError("DATE_NOT_ALLOWED", "No se puede cerrar un día futuro.")
    service_day = sites.get_service_day(db, site_id, day)
    if service_day is None:
        raise BusinessRuleError("SERVICE_DAY_NOT_OPENED")
    if service_day.status != "OPEN":
        raise BusinessRuleError("SERVICE_DAY_CLOSED")
    appointments = list(
        db.scalars(
            select(Appointment)
            .where(Appointment.service_day_id == service_day.id)
            .order_by(Appointment.ticket_number)
            .with_for_update(of=Appointment, key_share=True)
        ).unique()
    )
    if any(a.status == Status.EN_ATENCION for a in appointments):
        raise BusinessRuleError("DAY_HAS_IN_SERVICE")
    reason = db.scalar(select(Reason).where(Reason.type == "NO_SHOW", Reason.code == "CIERRE_JORNADA"))
    assert reason is not None, "Falta el motivo CIERRE_JORNADA (migración 0006)"

    now = clock.now()
    req = get_request_context()
    closed = 0
    for appt in appointments:
        if appt.status not in _PENDING:
            continue
        previous = appt.status
        appt.status = Status.NO_PRESENTADO
        appt.closed_at, appt.closed_by = now, ctx.user.id
        appt.close_reason = reason
        db.add(
            AppointmentEvent(
                appointment_id=appt.id,
                action="CLOSE_DAY" if previous != Status.LLAMADO else "NO_SHOW",
                from_status=previous,
                to_status=Status.NO_PRESENTADO,
                reason_id=reason.id,
                note="Cierre de jornada",
                occurred_at=now,
                user_id=ctx.user.id,
                ip=req.ip,
                request_id=req.request_id,
            )
        )
        closed += 1
    db.flush()
    service_day.status = "CLOSED"
    service_day.closed_at, service_day.closed_by = now, ctx.user.id
    pause = active_pause(db, site_id)
    if pause is not None:
        end_pause(db, pause, now, ctx.user.id)
    db.flush()

    snap = queue_view.build_snapshot(db, site, day, clock)
    counts = snap.counts
    recipients = _summary_recipients(db, site_id, ctx.user.id) if get_bool(db, "day_close.send_summary", True) else []
    if recipients:
        flt = reports.ReportFilter(day, day, [site_id])
        brand = branding.get_branding(db)
        meta = documents.ReportMeta(
            institution=brand.institution_name,
            date_from=day,
            date_to=day,
            site_names=[site.name],
            generated_at=now,
            generated_by=ctx.user.full_name,
            brand_color=brand.primary_color,
            org_name=brand.org_name,
            logo=branding.logo_bytes(db),
        )
        pdf = documents.summary_pdf(reports.summary(db, flt), meta)
        context = {
            "site_name": site.name,
            "service_date": f"{day:%d/%m/%Y}",
            "attended": counts["attended"],
            "no_show": counts["no_show"],
            "cancelled": counts["cancelled"],
            "closed_by": ctx.user.full_name,
            "institution_name": meta.institution,
        }
        for email in recipients:
            notifications.enqueue_direct(
                db,
                template_code="DAY_SUMMARY",
                recipient=email,
                context=context,
                now=now,
                created_by=ctx.user.id,
                dedup_key=f"DAY_SUMMARY:{service_day.id}:{email}"[:120],
                attachment=(f"resumen_{site.code.lower()}_{day:%Y%m%d}.pdf", "application/pdf", pdf),
            )
    ctx.audit(
        action="SERVICE_DAY_CLOSE",
        resource_type="service_day",
        resource_id=service_day.id,
        site_id=site_id,
        after={
            "service_date": day,
            "marked_no_show": closed,
            "attended": counts["attended"],
            "summary_sent_to": len(recipients),
        },
    )
    db.commit()
    return {
        "service_date": day,
        "marked_no_show": closed,
        "attended": counts["attended"],
        "no_show": counts["no_show"],
        "cancelled": counts["cancelled"],
        "summary_sent_to": len(recipients),
    }


def _summary_recipients(db: Session, site_id: int, closer_id: int) -> list[str]:
    """Supervisoras activas de la sede con correo, más quien cierra (si tiene correo)."""
    supervisors = db.scalars(
        select(AppUser.email)
        .join(user_role, user_role.c.user_id == AppUser.id)
        .join(Role, Role.id == user_role.c.role_id)
        .join(user_site, user_site.c.user_id == AppUser.id)
        .where(Role.code == "SUPERVISOR", AppUser.is_active, user_site.c.site_id == site_id, AppUser.email.is_not(None))
    )
    emails = {e.strip().lower() for e in supervisors if e}
    closer = db.scalar(select(AppUser.email).where(AppUser.id == closer_id))
    if closer:
        emails.add(closer.strip().lower())
    return sorted(emails)


# ================================================================== panel en vivo (2.5)


def live_board(ctx: ServiceContext) -> list[dict[str, Any]]:
    db, clock = ctx.db, ctx.clock
    today, now = clock.today(), clock.now()
    rows = []
    for site in db.scalars(select(Site).where(Site.id.in_(ctx.user.site_ids), Site.is_active).order_by(Site.id)):
        snap = queue_view.build_snapshot(db, site, today, clock)
        waiting_since = [i.appointment.queued_at or i.appointment.registered_at for i in snap.waiting + snap.called]
        attended = [i.appointment for i in snap.finished if i.appointment.started_at]
        avg_wait = (
            sum((a.started_at - a.registered_at).total_seconds() for a in attended if a.started_at) / 60 / len(attended)
            if attended
            else None
        )
        pause = active_pause(db, site.id)
        rows.append(
            {
                "site_id": site.id,
                "site_code": site.code,
                "site_name": site.name,
                "day_status": snap.service_day.status if snap.service_day else None,
                "counts": snap.counts,
                "longest_wait_minutes": int((now - min(waiting_since)).total_seconds() // 60)
                if waiting_since
                else None,
                "avg_wait_minutes": round(avg_wait, 1) if avg_wait is not None else None,
                "in_service": [
                    {
                        "ticket_code": i.appointment.ticket_code,
                        "doctor_name": i.appointment.doctor.full_name if i.appointment.doctor else None,
                        "room_name": i.appointment.room.name if i.appointment.room else None,
                        "started_at": i.appointment.started_at,
                    }
                    for i in snap.in_service
                ],
                "next_ticket_code": snap.waiting[0].appointment.ticket_code if snap.waiting else None,
                "pause": {"reason": pause.reason, "resume_at": pause.resume_at} if pause else None,
                "incidents": [{"code": i.code, "message": i.message} for i in snap.incidents],
            }
        )
    return rows


# ================================================================== mensajes de sala (2.7)


def display_messages_for(db: Session, site_id: int, today: date) -> list[str]:
    rows = db.scalars(
        select(DisplayMessage)
        .where(
            DisplayMessage.is_active,
            or_(DisplayMessage.site_id.is_(None), DisplayMessage.site_id == site_id),
            DisplayMessage.valid_from <= today,
            or_(DisplayMessage.valid_to.is_(None), DisplayMessage.valid_to >= today),
        )
        .order_by(DisplayMessage.sort_order, DisplayMessage.id)
    )
    return [m.text for m in rows]


def _check_message_scope(ctx: ServiceContext, site_id: int | None, action: str) -> None:
    if site_id is None:
        ctx.require_permission("site:manage", action=action)  # mensajes para todas las sedes
    else:
        ctx.require_site(site_id, action=action)


def create_message(ctx: ServiceContext, data: dict[str, Any]) -> DisplayMessage:
    _check_message_scope(ctx, data.get("site_id"), "DISPLAY_MESSAGE_CREATE")
    message = DisplayMessage(**data, created_by=ctx.user.id, updated_by=ctx.user.id)
    ctx.db.add(message)
    ctx.db.flush()
    ctx.audit(
        action="DISPLAY_MESSAGE_CREATE",
        resource_type="display_message",
        resource_id=message.id,
        site_id=message.site_id,
        after={k: v for k, v in data.items()},
    )
    ctx.db.commit()
    return message


def update_message(ctx: ServiceContext, message_id: int, changes: dict[str, Any]) -> DisplayMessage:
    message = ctx.db.get(DisplayMessage, message_id)
    if message is None:
        raise NotFoundError("DISPLAY_MESSAGE_NOT_FOUND")
    _check_message_scope(ctx, message.site_id, "DISPLAY_MESSAGE_UPDATE")
    before = {k: getattr(message, k) for k in changes}
    for key, value in changes.items():
        setattr(message, key, value)
    message.updated_by = ctx.user.id
    ctx.db.flush()
    ctx.audit(
        action="DISPLAY_MESSAGE_UPDATE",
        resource_type="display_message",
        resource_id=message.id,
        site_id=message.site_id,
        before=before,
        after=changes,
    )
    ctx.db.commit()
    return message


def list_messages(ctx: ServiceContext, site_id: int | None) -> list[DisplayMessage]:
    stmt = select(DisplayMessage)
    if site_id is not None:
        ctx.require_site(site_id, action="DISPLAY_MESSAGE_READ")
        stmt = stmt.where(or_(DisplayMessage.site_id.is_(None), DisplayMessage.site_id == site_id))
    else:
        stmt = stmt.where(or_(DisplayMessage.site_id.is_(None), DisplayMessage.site_id.in_(ctx.user.site_ids)))
    return list(
        ctx.db.scalars(stmt.order_by(DisplayMessage.is_active.desc(), DisplayMessage.sort_order, DisplayMessage.id))
    )
