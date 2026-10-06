"""Disponibilidad de médicos: presentes (sin ausencia), de turno (según su horario) y capacidad calculada.

Reglas:
- Un médico SIN bloques de horario se considera disponible durante todo el horario de la sede.
- Un médico con ausencia que cubre la fecha no está presente ese día.
- Capacidad por médicos (parámetro capacity.by_doctor_schedule): solo si algún médico activo de la sede
  tiene horario. Minutos de atención de los médicos presentes ÷ duración del turno, sin superar la
  capacidad configurada de la sede.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.admin.parameters import get_bool
from app.modules.sites.models import Doctor, DoctorAbsence, DoctorSchedule

AUTO_CAPACITY_REASON = "Automático: según los médicos presentes"


@dataclass(frozen=True)
class DoctorDay:
    doctor: Doctor
    blocks: list[tuple[time, time]]  # bloques del día (vacío si el médico no tiene horario definido)
    has_schedule: bool
    absence_reason: str | None

    @property
    def present(self) -> bool:
        """Activo y sin ausencia; si tiene horario, debe atender ese día de la semana."""
        return self.doctor.is_active and self.absence_reason is None and (not self.has_schedule or bool(self.blocks))

    def on_duty_at(self, moment: time) -> bool:
        if not self.present:
            return False
        return not self.has_schedule or any(start <= moment < end for start, end in self.blocks)


def doctors_for_day(db: Session, site_id: int, day: date) -> list[DoctorDay]:
    doctors = list(db.scalars(select(Doctor).where(Doctor.site_id == site_id).order_by(Doctor.full_name)))
    if not doctors:
        return []
    ids = [d.id for d in doctors]
    schedule: dict[int, list[DoctorSchedule]] = defaultdict(list)
    for row in db.scalars(select(DoctorSchedule).where(DoctorSchedule.doctor_id.in_(ids))):
        schedule[row.doctor_id].append(row)
    absences = {
        a.doctor_id: a.reason
        for a in db.scalars(
            select(DoctorAbsence).where(
                DoctorAbsence.doctor_id.in_(ids), DoctorAbsence.date_from <= day, DoctorAbsence.date_to >= day
            )
        )
    }
    weekday = day.isoweekday()
    return [
        DoctorDay(
            doctor=d,
            blocks=sorted((r.start_time, r.end_time) for r in schedule[d.id] if r.weekday == weekday),
            has_schedule=bool(schedule[d.id]),
            absence_reason=absences.get(d.id),
        )
        for d in doctors
    ]


def assignable(db: Session, site_id: int, day: date, local_now: datetime) -> tuple[list[Doctor], list[Doctor]]:
    """(presentes hoy, de turno ahora) entre los médicos activos de la sede."""
    days = doctors_for_day(db, site_id, day)
    present = [d.doctor for d in days if d.present]
    on_duty = [d.doctor for d in days if d.on_duty_at(local_now.time())]
    return present, on_duty


def planned_capacity(
    db: Session,
    site_id: int,
    day: date,
    *,
    base_capacity: int,
    slot_minutes: int,
    site_blocks: list[tuple[time, time]],
) -> int | None:
    """Capacidad según médicos presentes, o None si no aplica (parámetro desactivado o sin horarios de médicos)."""
    if not get_bool(db, "capacity.by_doctor_schedule", True):
        return None
    days = [d for d in doctors_for_day(db, site_id, day) if d.doctor.is_active]
    if not any(d.has_schedule for d in days):
        return None
    site_minutes = sum(_minutes(s, e) for s, e in site_blocks)
    minutes = 0
    for d in days:
        if not d.present:
            continue
        minutes += sum(_minutes(s, e) for s, e in d.blocks) if d.has_schedule else site_minutes
    return min(base_capacity, minutes // max(slot_minutes, 1))


def _minutes(start: time, end: time) -> int:
    return (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)
