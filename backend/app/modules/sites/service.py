"""Sedes: configuración vigente, horarios, cierres, disponibilidad y ventana de registro."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.modules.admin.parameters import get_int
from app.modules.appointments.models import ServiceDay
from app.modules.sites import doctors
from app.modules.sites.models import Site, SiteClosure, SiteSchedule, SiteSettingVersion


@dataclass(frozen=True)
class Block:
    block: str
    start: time
    end: time


def get_site(db: Session, site_id: int, *, active_only: bool = False) -> Site:
    site = db.get(Site, site_id)
    if site is None:
        raise NotFoundError("SITE_NOT_FOUND")
    if active_only and not site.is_active:
        raise BusinessRuleError("SITE_INACTIVE")
    return site


def effective_setting(db: Session, site_id: int, day: date) -> SiteSettingVersion | None:
    return db.scalar(
        select(SiteSettingVersion)
        .where(SiteSettingVersion.site_id == site_id, SiteSettingVersion.valid_from <= day)
        .order_by(SiteSettingVersion.valid_from.desc())
        .limit(1)
    )


def setting_history(db: Session, site_id: int) -> list[SiteSettingVersion]:
    return list(
        db.scalars(
            select(SiteSettingVersion)
            .where(SiteSettingVersion.site_id == site_id)
            .order_by(SiteSettingVersion.valid_from.desc())
        )
    )


def _schedule_valid_on(day: date) -> object:
    return and_(SiteSchedule.valid_from <= day, or_(SiteSchedule.valid_to.is_(None), SiteSchedule.valid_to >= day))


def schedule_rows(db: Session, site_id: int, day: date) -> list[SiteSchedule]:
    """Filas de horario vigentes en la fecha (todos los días de la semana)."""
    return list(
        db.scalars(
            select(SiteSchedule)
            .where(SiteSchedule.site_id == site_id, _schedule_valid_on(day))  # type: ignore[arg-type]
            .order_by(SiteSchedule.weekday, SiteSchedule.start_time)
        )
    )


def blocks_for(db: Session, site_id: int, day: date) -> list[Block]:
    rows = db.scalars(
        select(SiteSchedule)
        .where(
            SiteSchedule.site_id == site_id,
            SiteSchedule.weekday == day.isoweekday(),
            _schedule_valid_on(day),  # type: ignore[arg-type]
        )
        .order_by(SiteSchedule.start_time)
    )
    return [Block(r.block, r.start_time, r.end_time) for r in rows]


def closure_on(db: Session, site_id: int, day: date) -> SiteClosure | None:
    return db.scalar(select(SiteClosure).where(SiteClosure.site_id == site_id, SiteClosure.closure_date == day))


def get_service_day(db: Session, site_id: int, day: date) -> ServiceDay | None:
    return db.scalar(select(ServiceDay).where(ServiceDay.site_id == site_id, ServiceDay.service_date == day))


def registration_blocker(db: Session, site: Site, day: date, clock: Clock) -> str | None:
    """Motivo (código de error) por el cual no se puede registrar en la sede/fecha; None si se puede."""
    today = clock.today()
    max_days = get_int(db, "booking.advance_days_max", 0)
    if not site.is_active:
        return "SITE_INACTIVE"
    if day < today or day > today + timedelta(days=max_days):
        return "DATE_NOT_ALLOWED"
    if closure_on(db, site.id, day) is not None:
        return "SITE_CLOSED_ON_DATE"
    blocks = blocks_for(db, site.id, day)
    if not blocks:
        return "SITE_NO_SCHEDULE"
    setting = effective_setting(db, site.id, day)
    if setting is None:
        return "SITE_NO_SCHEDULE"
    if day == today:
        last_end = clock.combine(day, blocks[-1].end)
        cutoff = last_end - timedelta(minutes=setting.registration_cutoff_minutes)
        if clock.now() >= cutoff:
            return "REGISTRATION_WINDOW_CLOSED"
    service_day = get_service_day(db, site.id, day)
    if service_day is not None:
        if service_day.status != "OPEN":
            return "SERVICE_DAY_CLOSED"
        if service_day.occupied_count >= service_day.capacity:
            return "CAPACITY_REACHED"
    elif new_day_capacity(db, site.id, day, setting, blocks) <= 0:
        return "NO_DOCTOR_AVAILABLE" if setting.daily_capacity > 0 else "CAPACITY_REACHED"
    return None


def new_day_capacity(
    db: Session, site_id: int, day: date, setting: SiteSettingVersion, blocks: list[Block] | None = None
) -> int:
    """Capacidad que tendrá un día aún no abierto: la configurada o la calculada por médicos presentes."""
    blocks = blocks if blocks is not None else blocks_for(db, site_id, day)
    planned = doctors.planned_capacity(
        db,
        site_id,
        day,
        base_capacity=setting.daily_capacity,
        slot_minutes=setting.slot_minutes,
        site_blocks=[(b.start, b.end) for b in blocks],
    )
    return setting.daily_capacity if planned is None else planned


def apply_planned_capacity(db: Session, service_day: ServiceDay, now: datetime, user_id: int) -> bool:
    """Recalcula la capacidad de un día abierto según los médicos presentes.

    No toca días ajustados manualmente por la supervisión ni baja de los cupos ya ocupados.
    """
    if service_day.status != "OPEN":
        return False
    if service_day.capacity_adjust_reason not in (None, doctors.AUTO_CAPACITY_REASON):
        return False
    setting = db.get(SiteSettingVersion, service_day.setting_version_id)
    if setting is None:  # pragma: no cover - FK
        return False
    blocks = blocks_for(db, service_day.site_id, service_day.service_date)
    planned = doctors.planned_capacity(
        db,
        service_day.site_id,
        service_day.service_date,
        base_capacity=setting.daily_capacity,
        slot_minutes=service_day.slot_minutes,
        site_blocks=[(b.start, b.end) for b in blocks],
    )
    target = setting.daily_capacity if planned is None else max(planned, service_day.occupied_count)
    if target == service_day.capacity:
        return False
    service_day.capacity = target
    service_day.capacity_adjusted_at = now
    service_day.capacity_adjusted_by = user_id
    service_day.capacity_adjust_reason = doctors.AUTO_CAPACITY_REASON
    return True


def refresh_planned_capacity(db: Session, site_id: int, clock: Clock, user_id: int) -> None:
    """Tras cambiar horarios o ausencias de médicos: recalcula los días abiertos desde hoy."""
    days = db.scalars(
        select(ServiceDay).where(
            ServiceDay.site_id == site_id, ServiceDay.service_date >= clock.today(), ServiceDay.status == "OPEN"
        )
    )
    for service_day in days:
        apply_planned_capacity(db, service_day, clock.now(), user_id)


@dataclass(frozen=True)
class Availability:
    site: Site
    service_date: date
    capacity: int
    occupied: int
    available: int
    day_status: str | None
    can_register: bool
    blocker: str | None
    blocks: list[Block]
    closure_reason: str | None


def availability(db: Session, site: Site, day: date, clock: Clock) -> Availability:
    service_day = get_service_day(db, site.id, day)
    setting = effective_setting(db, site.id, day)
    planned = new_day_capacity(db, site.id, day, setting) if setting else 0
    capacity = service_day.capacity if service_day else planned
    occupied = service_day.occupied_count if service_day else 0
    closure = closure_on(db, site.id, day)
    blocker = registration_blocker(db, site, day, clock)
    return Availability(
        site=site,
        service_date=day,
        capacity=capacity,
        occupied=occupied,
        available=max(capacity - occupied, 0),
        day_status=service_day.status if service_day else None,
        can_register=blocker is None,
        blocker=blocker,
        blocks=blocks_for(db, site.id, day),
        closure_reason=closure.reason if closure else None,
    )


def block_windows(clock: Clock, day: date, blocks: list[Block]) -> list[tuple[datetime, datetime]]:
    return [(clock.combine(day, b.start), clock.combine(day, b.end)) for b in blocks]


def ensure_future_date(clock: Clock, valid_from: date) -> None:
    """Los cambios de configuración/horario aplican desde mañana (RN-08)."""
    if valid_from <= clock.today():
        raise BusinessRuleError(
            "DATE_NOT_ALLOWED",
            "Los cambios de configuración deben aplicar a partir de una fecha futura (desde mañana).",
        )


def assert_no_future_schedule_after(db: Session, site_id: int, valid_from: date) -> None:
    pending = db.scalar(
        select(SiteSchedule.valid_from)
        .where(SiteSchedule.site_id == site_id, SiteSchedule.valid_from >= valid_from)
        .limit(1)
    )
    if pending is not None:
        raise ConflictError(
            "SCHEDULE_OVERLAP", f"Ya existe un horario programado a partir del {pending:%d/%m/%Y}; ajústelo primero."
        )
