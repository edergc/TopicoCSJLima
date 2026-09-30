"""Vista de la cola de un día: orden, posiciones, horas estimadas, indicadores e incidencias."""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.modules.appointments.models import Appointment, ServiceDay
from app.modules.appointments.scheduling import estimate_start_times
from app.modules.appointments.state_machine import Status
from app.modules.notifications.models import Notification
from app.modules.sites import service as sites
from app.modules.sites.models import Site

LOW_CAPACITY_THRESHOLD = 2


@dataclass
class QueueItem:
    appointment: Appointment
    position: int | None = None
    people_ahead: int | None = None
    estimated_at: datetime | None = None
    tolerance_expires_at: datetime | None = None


@dataclass
class Incident:
    code: str
    message: str
    ticket_code: str | None = None


@dataclass
class QueueSnapshot:
    site: Site
    service_date: date
    service_day: ServiceDay | None
    capacity: int
    in_service: list[QueueItem] = field(default_factory=list)
    called: list[QueueItem] = field(default_factory=list)
    waiting: list[QueueItem] = field(default_factory=list)
    registered: list[QueueItem] = field(default_factory=list)
    finished: list[QueueItem] = field(default_factory=list)
    closed: list[QueueItem] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    incidents: list[Incident] = field(default_factory=list)

    def item_for(self, appointment_id: int) -> QueueItem | None:
        for group in (self.in_service, self.called, self.waiting, self.registered, self.finished, self.closed):
            for item in group:
                if item.appointment.id == appointment_id:
                    return item
        return None


def day_appointments(db: Session, service_day_id: int) -> list[Appointment]:
    return list(
        db.scalars(
            select(Appointment).where(Appointment.service_day_id == service_day_id).order_by(Appointment.ticket_number)
        ).unique()
    )


def build_snapshot(db: Session, site: Site, day: date, clock: Clock) -> QueueSnapshot:
    service_day = sites.get_service_day(db, site.id, day)
    setting = sites.effective_setting(db, site.id, day)
    capacity = service_day.capacity if service_day else (setting.daily_capacity if setting else 0)
    snap = QueueSnapshot(site=site, service_date=day, service_day=service_day, capacity=capacity)
    appointments = day_appointments(db, service_day.id) if service_day else []

    tolerance = timedelta(minutes=service_day.tolerance_minutes if service_day else 0)
    for appt in appointments:
        item = QueueItem(appt)
        match appt.status:
            case Status.EN_ATENCION:
                snap.in_service.append(item)
            case Status.LLAMADO:
                item.tolerance_expires_at = appt.called_at + tolerance if appt.called_at else None
                snap.called.append(item)
            case Status.EN_ESPERA:
                snap.waiting.append(item)
            case Status.REGISTRADO:
                snap.registered.append(item)
            case Status.ATENDIDO:
                snap.finished.append(item)
            case _:
                snap.closed.append(item)
    snap.called.sort(key=lambda i: i.appointment.called_at or i.appointment.registered_at)

    now = clock.now()
    if service_day is not None:
        # Primero se atiende a los llamados, luego a quienes esperan (orden de turno).
        pending = snap.called + snap.waiting + snap.registered
        estimates = estimate_start_times(
            now=now,
            blocks=sites.block_windows(clock, day, sites.blocks_for(db, site.id, day)),
            slot_minutes=service_day.slot_minutes,
            lanes=service_day.max_concurrent_in_service,
            in_service_started=[i.appointment.started_at for i in snap.in_service if i.appointment.started_at],
            pending_count=len(pending),
        )
        for index, (item, estimate) in enumerate(zip(pending, estimates, strict=True)):
            item.estimated_at = estimate
            if item.appointment.status != Status.LLAMADO:
                item.people_ahead = index
                item.position = index + 1

    by_status = {s.value: 0 for s in Status}
    for appt in appointments:
        by_status[appt.status] += 1
    occupied = service_day.occupied_count if service_day else 0
    snap.counts = {
        "capacity": capacity,
        "occupied": occupied,
        "available": max(capacity - occupied, 0),
        "total": len(appointments),
        "registered": by_status[Status.REGISTRADO],
        "waiting": by_status[Status.EN_ESPERA],
        "called": by_status[Status.LLAMADO],
        "in_service": by_status[Status.EN_ATENCION],
        "attended": by_status[Status.ATENDIDO],
        "cancelled": by_status[Status.CANCELADO],
        "no_show": by_status[Status.NO_PRESENTADO],
        "voided": by_status[Status.ANULADO],
    }
    snap.incidents = _incidents(db, snap, now)
    return snap


def _incidents(db: Session, snap: QueueSnapshot, now: datetime) -> list[Incident]:
    incidents: list[Incident] = []
    for item in snap.called:
        if item.tolerance_expires_at and now >= item.tolerance_expires_at:
            incidents.append(
                Incident(
                    "TOLERANCE_EXPIRED",
                    f"{item.appointment.ticket_code}: venció la tolerancia desde el llamado.",
                    item.appointment.ticket_code,
                )
            )
    available = snap.counts["available"]
    if snap.service_day is not None and available == 0:
        incidents.append(Incident("CAPACITY_FULL", "Se alcanzó la capacidad máxima del día."))
    elif snap.service_day is not None and available <= LOW_CAPACITY_THRESHOLD:
        incidents.append(Incident("CAPACITY_LOW", f"Quedan {available} cupo(s) disponibles."))
    if snap.service_day is not None:
        failed = db.scalar(
            select(func.count())
            .select_from(Notification)
            .join(Appointment, Appointment.id == Notification.appointment_id)
            .where(Appointment.service_day_id == snap.service_day.id, Notification.status == "FAILED")
        )
        if failed:
            incidents.append(Incident("NOTIFICATIONS_FAILED", f"{failed} correo(s) no pudieron enviarse."))
    return incidents
