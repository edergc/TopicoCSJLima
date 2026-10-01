import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.modules.appointments import queue as queue_view
from app.modules.appointments.models import Appointment, AppointmentStatus, Reason
from app.modules.appointments.schemas import (
    AppointmentCreateIn,
    AppointmentEventOut,
    AppointmentOut,
    IncidentOut,
    NotificationOut,
    QueueCountsOut,
    QueueOut,
    ReasonOut,
    StatusOut,
    TransitionIn,
    WorkerBriefOut,
)
from app.modules.appointments.service import AppointmentService
from app.modules.appointments.state_machine import Action, allowed_actions
from app.modules.auth.dependencies import ServiceContext, require
from app.modules.notifications.models import Notification
from app.modules.sites import service as sites
from app.modules.users.models import AppUser
from app.shared.schemas import Page, PageParams
from app.shared.text import display_name, short_name

router = APIRouter(tags=["Atenciones y cola"])

ReadCtx = Annotated[ServiceContext, Depends(require("appointment:read"))]


def mask_email(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    user, domain = email.split("@", 1)
    return f"{user[:1]}***@{domain}"


def appointment_out(a: Appointment, ctx: ServiceContext, item: queue_view.QueueItem | None = None) -> AppointmentOut:
    w = a.worker
    return AppointmentOut(
        public_id=a.public_id,
        ticket_code=a.ticket_code,
        ticket_number=a.ticket_number,
        status=a.status,
        channel=a.channel,
        site_id=a.site_id,
        site_name=a.site.name,
        service_date=a.service_date,
        worker=WorkerBriefOut(
            public_id=w.public_id,
            document_number=w.document_number,
            display_name=display_name(w.first_names, w.paternal_surname, w.maternal_surname),
            short_name=short_name(w.first_names, w.paternal_surname, w.maternal_surname),
            department_name=w.department.name if w.department else None,
            has_email=bool(w.institutional_email),
        ),
        registered_at=a.registered_at,
        queued_at=a.queued_at,
        called_at=a.called_at,
        call_count=a.call_count,
        started_at=a.started_at,
        finished_at=a.finished_at,
        closed_at=a.closed_at,
        close_reason=ReasonOut.model_validate(a.close_reason) if a.close_reason else None,
        close_note=a.close_note,
        admin_note=a.admin_note,
        doctor_id=a.doctor_id,
        doctor_name=a.doctor.full_name if a.doctor else None,
        version=a.version,
        allowed_actions=allowed_actions(a.status, ctx.user.permissions),
        position=item.position if item else None,
        people_ahead=item.people_ahead if item else None,
        estimated_at=item.estimated_at if item else None,
        tolerance_expires_at=item.tolerance_expires_at if item else None,
    )


# ------------------------------------------------------------------- cola


@router.get("/sites/{site_id}/queue", response_model=QueueOut, summary="Cola del día + indicadores (panel operativo)")
def get_queue(
    site_id: int,
    ctx: Annotated[ServiceContext, Depends(require("queue:read"))],
    date_: Annotated[date | None, Query(alias="date")] = None,
) -> QueueOut:
    ctx.require_site(site_id, action="QUEUE_READ")
    site = sites.get_site(ctx.db, site_id)
    snap = queue_view.build_snapshot(ctx.db, site, date_ or ctx.clock.today(), ctx.clock)

    def items(group: list[queue_view.QueueItem]) -> list[AppointmentOut]:
        return [appointment_out(i.appointment, ctx, i) for i in group]

    return QueueOut(
        site_id=site.id,
        site_name=site.name,
        service_date=snap.service_date,
        generated_at=ctx.clock.now(),
        day_status=snap.service_day.status if snap.service_day else None,
        next_ticket_code=snap.waiting[0].appointment.ticket_code if snap.waiting else None,
        counts=QueueCountsOut(**snap.counts),
        in_service=items(snap.in_service),
        called=items(snap.called),
        waiting=items(snap.waiting),
        registered=items(snap.registered),
        finished=items(snap.finished),
        closed=items(snap.closed),
        incidents=[IncidentOut(code=i.code, message=i.message, ticket_code=i.ticket_code) for i in snap.incidents],
    )


@router.post("/sites/{site_id}/queue/call-next", response_model=AppointmentOut, summary="LLAMAR SIGUIENTE")
def call_next(site_id: int, ctx: Annotated[ServiceContext, Depends(require("appointment:operate"))]) -> AppointmentOut:
    return appointment_out(AppointmentService(ctx).call_next(site_id), ctx)


# ------------------------------------------------------------- atenciones


@router.post(
    "/appointments", response_model=AppointmentOut, status_code=201, summary="Registrar atención (genera turno)"
)
def register(
    body: AppointmentCreateIn, ctx: Annotated[ServiceContext, Depends(require("appointment:create"))]
) -> AppointmentOut:
    service = AppointmentService(ctx)
    appointment = service.register(body)
    snap = queue_view.build_snapshot(ctx.db, appointment.site, appointment.service_date, ctx.clock)
    return appointment_out(appointment, ctx, snap.item_for(appointment.id))


@router.get("/appointments", response_model=Page[AppointmentOut], summary="Buscar atenciones")
def search(
    ctx: ReadCtx,
    paging: Annotated[PageParams, Depends()],
    site_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    status: str | None = Query(default=None, max_length=15),
    document_number: str | None = Query(default=None, max_length=12),
) -> Page[AppointmentOut]:
    rows, total = AppointmentService(ctx).search(
        site_id=site_id,
        date_from=date_from,
        date_to=date_to,
        status=status,
        document_number=document_number,
        offset=paging.offset,
        limit=paging.size,
    )
    return Page(items=[appointment_out(a, ctx) for a in rows], total=total, page=paging.page, size=paging.size)


@router.get("/appointments/{public_id}", response_model=AppointmentOut)
def get_appointment(public_id: uuid.UUID, ctx: ReadCtx) -> AppointmentOut:
    appointment = AppointmentService(ctx).get(public_id)
    snap = queue_view.build_snapshot(ctx.db, appointment.site, appointment.service_date, ctx.clock)
    return appointment_out(appointment, ctx, snap.item_for(appointment.id))


@router.get("/appointments/{public_id}/events", response_model=list[AppointmentEventOut], summary="Línea de tiempo")
def get_events(public_id: uuid.UUID, ctx: ReadCtx) -> list[AppointmentEventOut]:
    events = AppointmentService(ctx).events(public_id)
    user_ids = {e.user_id for e in events if e.user_id}
    names = dict(ctx.db.execute(select(AppUser.id, AppUser.full_name).where(AppUser.id.in_(user_ids))).tuples().all())
    return [
        AppointmentEventOut(
            action=e.action,
            from_status=e.from_status,
            to_status=e.to_status,
            reason_label=e.reason.label if e.reason else None,
            note=e.note,
            occurred_at=e.occurred_at,
            user_name=names.get(e.user_id) if e.user_id else "Sistema",
        )
        for e in events
    ]


@router.get("/appointments/{public_id}/notifications", response_model=list[NotificationOut])
def get_notifications(
    public_id: uuid.UUID, ctx: Annotated[ServiceContext, Depends(require("notification:read"))]
) -> list[NotificationOut]:
    appointment = AppointmentService(ctx).get(public_id)
    rows = ctx.db.scalars(
        select(Notification).where(Notification.appointment_id == appointment.id).order_by(Notification.id)
    )
    return [notification_out(n) for n in rows]


def notification_out(n: Notification) -> NotificationOut:
    return NotificationOut(
        id=n.id,
        template_code=n.template_code,
        channel=n.channel,
        status=n.status,
        recipient_masked=mask_email(n.recipient),
        subject=n.subject,
        attempts=n.attempts,
        last_error=n.last_error,
        sent_at=n.sent_at,
        created_at=n.created_at,
    )


def _transition_endpoint(action: Action, summary: str) -> None:
    def endpoint(
        public_id: uuid.UUID, body: TransitionIn, ctx: Annotated[ServiceContext, Depends(require())]
    ) -> AppointmentOut:
        appointment = AppointmentService(ctx).transition(public_id, action, body)
        snap = queue_view.build_snapshot(ctx.db, appointment.site, appointment.service_date, ctx.clock)
        return appointment_out(appointment, ctx, snap.item_for(appointment.id))

    path = action.value.lower().replace("_", "-")
    endpoint.__name__ = f"appointment_{action.value.lower()}"
    router.add_api_route(
        f"/appointments/{{public_id}}/{path}",
        endpoint,
        methods=["POST"],
        response_model=AppointmentOut,
        summary=summary,
    )


_transition_endpoint(Action.CALL, "Llamar (EN_ESPERA → LLAMADO)")
_transition_endpoint(Action.REQUEUE, "Devolver a la cola (LLAMADO → EN_ESPERA, conserva su turno)")
_transition_endpoint(Action.START, "Iniciar atención (LLAMADO → EN_ATENCION)")
_transition_endpoint(Action.FINISH, "Finalizar atención (EN_ATENCION → ATENDIDO)")
_transition_endpoint(Action.CANCEL, "Cancelar (libera el cupo)")
_transition_endpoint(Action.NO_SHOW, "Marcar no presentado (tras la tolerancia; libera el cupo)")
_transition_endpoint(Action.VOID, "Anular por error de registro (libera el cupo)")


# -------------------------------------------------------------- catálogos

catalog_router = APIRouter(prefix="/catalogs", tags=["Catálogos"])


@catalog_router.get("/reasons", response_model=list[ReasonOut], summary="Motivos activos por tipo")
def list_reasons(
    ctx: Annotated[ServiceContext, Depends(require())],
    type_: Annotated[str | None, Query(alias="type", max_length=15)] = None,
) -> list[Reason]:
    stmt = select(Reason).where(Reason.is_active)
    if type_:
        stmt = stmt.where(Reason.type == type_)
    return list(ctx.db.scalars(stmt.order_by(Reason.type, Reason.sort_order)))


@catalog_router.get("/appointment-statuses", response_model=list[StatusOut], summary="Estados de la atención")
def list_statuses(ctx: Annotated[ServiceContext, Depends(require())]) -> list[AppointmentStatus]:
    return list(ctx.db.scalars(select(AppointmentStatus).order_by(AppointmentStatus.sort_order)))
