"""Endpoints públicos (sin iniciar sesión).

1. Consulta del estado del turno (trabajador, desde su celular).
2. Pantalla de turnos de la sala de espera (TV): quién está siendo llamado y quiénes siguen.

Seguridad y privacidad de la consulta:
- Exige DNI + código de turno (ambos): no se puede consultar a terceros solo con un DNI.
- Respuesta genérica si no coincide (no revela si el DNI existe).
- Rate limit por IP.
- Nunca devuelve datos de otras personas; el nombre propio se muestra enmascarado.

Privacidad de la pantalla: solo código de turno y nombre abreviado ("María G.", desactivable por
parámetro). Nunca DNI, correo, dependencia ni datos de salud. Es la misma información que se
anunciaría en voz alta en la sala.
"""

import re
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.core.ratelimit import limiter
from app.modules.admin.parameters import get_bool, get_str
from app.modules.appointments import queue as queue_view
from app.modules.appointments.models import Appointment, AppointmentStatus
from app.modules.appointments.queue import QueueItem
from app.modules.auth.dependencies import ClockDep, DbDep
from app.modules.sites.models import Site
from app.modules.workers.models import Worker
from app.shared.schemas import ApiOut
from app.shared.text import is_valid_dni, mask_name, normalize_document, short_name

router = APIRouter(prefix="/public", tags=["Consulta pública"])

_TICKET_RE = re.compile(r"^[A-Z]{1,3}-\d{3}$")


class PublicTicketStatusOut(ApiOut):
    ticket_code: str
    status: str
    status_label: str
    status_description: str
    site_name: str
    location_note: str | None
    service_date: date
    registered_at: datetime
    worker_name: str
    position: int | None
    people_ahead: int | None
    estimated_at: datetime | None
    updated_at: datetime


@router.get("/ticket-status", response_model=PublicTicketStatusOut, summary="Consultar el estado de mi turno")
@limiter.limit("20/minute")
def ticket_status(
    request: Request,
    db: DbDep,
    clock: ClockDep,
    document_number: Annotated[str, Query(min_length=5, max_length=12)],
    ticket_code: Annotated[str, Query(min_length=5, max_length=7)],
) -> PublicTicketStatusOut:
    if not get_bool(db, "public_status.enabled", True):
        raise NotFoundError("PUBLIC_STATUS_DISABLED")
    dni = normalize_document(document_number)
    code = ticket_code.strip().upper()
    if not is_valid_dni(dni) or not _TICKET_RE.match(code):
        raise NotFoundError("PUBLIC_TICKET_NOT_FOUND")

    appointment = db.scalar(
        select(Appointment)
        .join(Worker, Worker.id == Appointment.worker_id)
        .where(
            Worker.document_number == dni,
            Appointment.ticket_code == code,
            Appointment.service_date >= clock.today(),
        )
        .order_by(Appointment.service_date)
        .limit(1)
    )
    if appointment is None:
        raise NotFoundError("PUBLIC_TICKET_NOT_FOUND")

    status = db.get(AppointmentStatus, appointment.status)
    assert status is not None
    snap = queue_view.build_snapshot(db, appointment.site, appointment.service_date, clock)
    item = snap.item_for(appointment.id)
    return PublicTicketStatusOut(
        ticket_code=appointment.ticket_code,
        status=appointment.status,
        status_label=status.label,
        status_description=status.description,
        site_name=appointment.site.name,
        location_note=appointment.site.location_note,
        service_date=appointment.service_date,
        registered_at=appointment.registered_at,
        worker_name=mask_name(appointment.worker.first_names, appointment.worker.paternal_surname),
        position=item.position if item else None,
        people_ahead=item.people_ahead if item else None,
        estimated_at=item.estimated_at if item else None,
        updated_at=clock.now(),
    )


# ---------------------------------------------------------------------------
# Pantalla de turnos (sala de espera)
# ---------------------------------------------------------------------------
_DISPLAY_WAITING_LIMIT = 8


class DisplaySiteOut(ApiOut):
    code: str
    name: str
    short_name: str
    location_note: str | None


class DisplayTicketOut(ApiOut):
    ticket_code: str
    name: str | None
    status: str
    called_at: datetime | None
    call_count: int
    estimated_at: datetime | None


class DisplayBoardOut(ApiOut):
    site: DisplaySiteOut
    service_date: date
    day_status: str | None
    show_names: bool
    voice_enabled: bool
    message: str
    calling: list[DisplayTicketOut]
    in_service: list[DisplayTicketOut]
    waiting: list[DisplayTicketOut]
    waiting_total: int
    attended_count: int
    generated_at: datetime


def _ensure_display_enabled(db: Session) -> None:
    if not get_bool(db, "display.enabled", True):
        raise NotFoundError("DISPLAY_DISABLED")


def _display_ticket(item: QueueItem, show_names: bool) -> DisplayTicketOut:
    appt = item.appointment
    return DisplayTicketOut(
        ticket_code=appt.ticket_code,
        name=short_name(appt.worker.first_names, appt.worker.paternal_surname, None) if show_names else None,
        status=appt.status,
        called_at=appt.called_at,
        call_count=appt.call_count,
        estimated_at=item.estimated_at,
    )


@router.get("/display/sites", response_model=list[DisplaySiteOut], summary="Sedes con pantalla de turnos")
@limiter.limit("60/minute")
def display_sites(request: Request, db: DbDep) -> list[Site]:
    _ensure_display_enabled(db)
    return list(db.scalars(select(Site).where(Site.is_active).order_by(Site.id)))


@router.get("/display/{site_code}", response_model=DisplayBoardOut, summary="Pantalla de turnos de una sede")
@limiter.limit("120/minute")
def display_board(request: Request, db: DbDep, clock: ClockDep, site_code: str) -> DisplayBoardOut:
    _ensure_display_enabled(db)
    site = db.scalar(select(Site).where(Site.code == site_code.strip().upper()[:10], Site.is_active))
    if site is None:
        raise NotFoundError("SITE_NOT_FOUND")
    show_names = get_bool(db, "display.show_names", True)
    snap = queue_view.build_snapshot(db, site, clock.today(), clock)
    # El llamado más reciente primero: es el que se muestra en grande.
    calling = sorted(snap.called, key=lambda i: i.appointment.called_at or clock.now(), reverse=True)
    pending = snap.waiting + snap.registered
    return DisplayBoardOut(
        site=DisplaySiteOut.model_validate(site),
        service_date=snap.service_date,
        day_status=snap.service_day.status if snap.service_day else None,
        show_names=show_names,
        voice_enabled=get_bool(db, "display.voice_enabled", True),
        message=get_str(db, "display.message", ""),
        calling=[_display_ticket(i, show_names) for i in calling],
        in_service=[_display_ticket(i, show_names) for i in snap.in_service],
        waiting=[_display_ticket(i, show_names) for i in pending[:_DISPLAY_WAITING_LIMIT]],
        waiting_total=len(pending),
        attended_count=snap.counts["attended"],
        generated_at=clock.now(),
    )
