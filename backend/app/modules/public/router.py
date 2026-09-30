"""Consulta pública del estado del turno (trabajador, sin iniciar sesión).

Seguridad y privacidad:
- Exige DNI + código de turno (ambos): no se puede consultar a terceros solo con un DNI.
- Respuesta genérica si no coincide (no revela si el DNI existe).
- Rate limit por IP.
- Nunca devuelve datos de otras personas; el nombre propio se muestra enmascarado.
"""

import re
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Query, Request
from sqlalchemy import select

from app.core.errors import NotFoundError
from app.core.ratelimit import limiter
from app.modules.admin.parameters import get_bool
from app.modules.appointments import queue as queue_view
from app.modules.appointments.models import Appointment, AppointmentStatus
from app.modules.auth.dependencies import ClockDep, DbDep
from app.modules.workers.models import Worker
from app.shared.schemas import ApiOut
from app.shared.text import is_valid_dni, mask_name, normalize_document

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
