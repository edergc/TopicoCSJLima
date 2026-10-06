"""Reportes agregados (sin datos personales) y listado nominal (permiso específico)."""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import Float, and_, cast, extract, func, select
from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleError
from app.modules.appointments.models import Appointment, ServiceDay
from app.modules.auth.dependencies import ServiceContext
from app.modules.sites.models import Doctor, Site
from app.modules.workers.models import Department, Worker

MAX_RANGE_DAYS = 366
LIMA = "America/Lima"


@dataclass(frozen=True)
class ReportFilter:
    date_from: date
    date_to: date
    site_ids: list[int]


def resolve_filter(
    ctx: ServiceContext, date_from: date | None, date_to: date | None, site_id: int | None
) -> ReportFilter:
    today = ctx.clock.today()
    date_to = date_to or today
    date_from = date_from or (date_to - timedelta(days=29))
    if date_from > date_to:
        raise BusinessRuleError("VALIDATION_ERROR", "La fecha inicial no puede ser posterior a la final.")
    if (date_to - date_from).days > MAX_RANGE_DAYS:
        raise BusinessRuleError("VALIDATION_ERROR", f"El rango máximo es de {MAX_RANGE_DAYS} días.")
    if site_id is not None:
        ctx.require_site(site_id, action="REPORT_READ")
        site_ids = [site_id]
    else:
        site_ids = sorted(ctx.user.site_ids)
    return ReportFilter(date_from, date_to, site_ids)


def _count(status: str) -> Any:
    return func.count().filter(Appointment.status == status)


def _minutes(later: Any, earlier: Any) -> Any:
    return cast(extract("epoch", later - earlier), Float) / 60.0


def summary(db: Session, f: ReportFilter) -> dict[str, Any]:
    base = and_(
        Appointment.site_id.in_(f.site_ids),
        Appointment.service_date.between(f.date_from, f.date_to),
        Appointment.channel != "MIGRATION",
    )
    totals = db.execute(
        select(
            func.count().filter(Appointment.status != "ANULADO").label("requested"),
            _count("ATENDIDO").label("attended"),
            _count("CANCELADO").label("cancelled"),
            _count("NO_PRESENTADO").label("no_show"),
            _count("ANULADO").label("voided"),
            func.count()
            .filter(Appointment.status.in_(("REGISTRADO", "EN_ESPERA", "LLAMADO", "EN_ATENCION")))
            .label("pending"),
            func.avg(_minutes(Appointment.started_at, Appointment.registered_at))
            .filter(Appointment.status == "ATENDIDO", Appointment.started_at.is_not(None))
            .label("avg_wait"),
            func.avg(_minutes(Appointment.finished_at, Appointment.started_at))
            .filter(Appointment.status == "ATENDIDO", Appointment.started_at.is_not(None))
            .label("avg_service"),
        ).where(base)
    ).one()
    capacity = (
        db.scalar(
            select(func.coalesce(func.sum(ServiceDay.capacity), 0)).where(
                ServiceDay.site_id.in_(f.site_ids), ServiceDay.service_date.between(f.date_from, f.date_to)
            )
        )
        or 0
    )

    by_day_rows = db.execute(
        select(
            Appointment.service_date,
            Appointment.site_id,
            func.count().filter(Appointment.status != "ANULADO"),
            _count("ATENDIDO"),
            _count("CANCELADO"),
            _count("NO_PRESENTADO"),
            _count("ANULADO"),
        )
        .where(base)
        .group_by(Appointment.service_date, Appointment.site_id)
        .order_by(Appointment.service_date, Appointment.site_id)
    ).all()
    day_capacity = {
        (d, s): c
        for d, s, c in db.execute(
            select(ServiceDay.service_date, ServiceDay.site_id, ServiceDay.capacity).where(
                ServiceDay.site_id.in_(f.site_ids), ServiceDay.service_date.between(f.date_from, f.date_to)
            )
        ).all()
    }
    site_names = dict(db.execute(select(Site.id, Site.short_name).where(Site.id.in_(f.site_ids))).tuples().all())

    hour = extract("hour", func.timezone(LIMA, Appointment.registered_at))
    by_hour = db.execute(
        select(hour.label("h"), func.count()).where(base, Appointment.status != "ANULADO").group_by("h").order_by("h")
    ).all()
    by_department = db.execute(
        select(func.coalesce(Department.name, "SIN DEPENDENCIA"), func.count())
        .select_from(Appointment)
        .join(Worker, Worker.id == Appointment.worker_id)
        .outerjoin(Department, Department.id == Worker.department_id)
        .where(base, Appointment.status != "ANULADO")
        .group_by(Department.name)
        .order_by(func.count().desc())
        .limit(20)
    ).all()
    by_channel = db.execute(
        select(Appointment.channel, func.count())
        .where(base, Appointment.status != "ANULADO")
        .group_by(Appointment.channel)
    ).all()

    by_doctor = db.execute(
        select(
            func.coalesce(Doctor.full_name, "Sin médico asignado"),
            func.count(),
            func.avg(_minutes(Appointment.finished_at, Appointment.started_at)),
        )
        .select_from(Appointment)
        .outerjoin(Doctor, Doctor.id == Appointment.doctor_id)
        .where(base, Appointment.status == "ATENDIDO")
        .group_by(Doctor.id, Doctor.full_name)
        .order_by(func.count().desc())
    ).all()

    def rnd(value: float | None) -> float | None:
        return round(float(value), 1) if value is not None else None

    return {
        "date_from": f.date_from,
        "date_to": f.date_to,
        "site_ids": f.site_ids,
        "totals": {
            "capacity": int(capacity),
            "requested": totals.requested,
            "attended": totals.attended,
            "cancelled": totals.cancelled,
            "no_show": totals.no_show,
            "voided": totals.voided,
            "pending": totals.pending,
            "utilization_pct": rnd(100.0 * totals.attended / capacity) if capacity else None,
            "no_show_pct": rnd(100.0 * totals.no_show / totals.requested) if totals.requested else None,
            "avg_wait_minutes": rnd(totals.avg_wait),
            "avg_service_minutes": rnd(totals.avg_service),
        },
        "by_day": [
            {
                "service_date": d,
                "site_id": s,
                "site_name": site_names.get(s, str(s)),
                "capacity": day_capacity.get((d, s), 0),
                "requested": req,
                "attended": att,
                "cancelled": can,
                "no_show": ns,
                "voided": vo,
            }
            for d, s, req, att, can, ns, vo in by_day_rows
        ],
        "by_hour": [{"hour": int(h), "count": c} for h, c in by_hour],
        "by_department": [{"department": name, "count": c} for name, c in by_department],
        "by_channel": [{"channel": ch, "count": c} for ch, c in by_channel],
        "by_doctor": [{"doctor": name, "attended": c, "avg_service_minutes": rnd(avg)} for name, c, avg in by_doctor],
    }


def nominal_rows(db: Session, f: ReportFilter) -> list[dict[str, Any]]:
    """Listado nominal (datos personales): solo con permiso report:read_nominal."""
    rows = db.execute(
        select(Appointment, Worker, Department.name, Site.short_name)
        .join(Worker, Worker.id == Appointment.worker_id)
        .join(Site, Site.id == Appointment.site_id)
        .outerjoin(Department, Department.id == Worker.department_id)
        .where(Appointment.site_id.in_(f.site_ids), Appointment.service_date.between(f.date_from, f.date_to))
        .order_by(Appointment.service_date, Appointment.site_id, Appointment.ticket_number)
    ).all()
    return [
        {
            "fecha": a.service_date,
            "sede": site,
            "turno": a.ticket_code,
            "estado": a.status,
            "canal": a.channel,
            "dni": w.document_number,
            "apellidos": " ".join(p for p in (w.paternal_surname, w.maternal_surname) if p),
            "nombres": w.first_names,
            "dependencia": dep or "",
            "registrado": a.registered_at,
            "llamado": a.called_at,
            "inicio": a.started_at,
            "fin": a.finished_at,
            "cierre": a.closed_at,
            "motivo_cierre": a.close_reason.label if a.close_reason else "",
            "medico": a.doctor.full_name if a.doctor else "",
            "consultorio": a.room.name if a.room else "",
        }
        for a, w, dep, site in rows
    ]
