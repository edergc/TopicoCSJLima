"""Prioridad explícita y auditable (requerimiento §11), desactivada por defecto.

Regla, cuando el parámetro priority.enabled está activo:
1. Entre quienes esperan, las atenciones prioritarias se llaman antes que las normales; dentro de cada
   grupo se respeta el orden de registro (número de turno).
2. Para que nadie espere indefinidamente, tras `priority.max_consecutive` llamados prioritarios seguidos
   se llama a la siguiente persona en orden normal (si la hay).
3. La prioridad solo la asigna una persona autorizada, con una categoría del catálogo (no diagnósticos),
   y cada asignación o retiro queda en la línea de tiempo y en la auditoría.

La pantalla de sala no muestra categorías de prioridad: solo el orden resultante.
"""

from collections.abc import Callable, Sequence
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.admin.parameters import get_bool, get_int
from app.modules.appointments.models import Appointment

T = TypeVar("T")


def enabled(db: Session) -> bool:
    return get_bool(db, "priority.enabled", False)


def max_consecutive(db: Session) -> int:
    return max(get_int(db, "priority.max_consecutive", 3), 1)


def call_order[T](items: Sequence[T], is_priority: Callable[[T], bool], streak: int, limit: int) -> list[T]:
    """Orden de llamado según la regla. `items` ya viene en orden de registro; `streak` = prioritarios seguidos."""
    priority = [i for i in items if is_priority(i)]
    normal = [i for i in items if not is_priority(i)]
    ordered: list[T] = []
    while priority or normal:
        if priority and (streak < limit or not normal):
            ordered.append(priority.pop(0))
            streak += 1
        else:
            ordered.append(normal.pop(0))
            streak = 0
    return ordered


def current_streak(db: Session, service_day_id: int, limit: int) -> int:
    """Cuántos de los últimos llamados del día fueron prioritarios, seguidos."""
    recent = db.scalars(
        select(Appointment.priority_reason_id)
        .where(Appointment.service_day_id == service_day_id, Appointment.called_at.is_not(None))
        .order_by(Appointment.called_at.desc())
        .limit(limit)
    )
    streak = 0
    for reason_id in recent:
        if reason_id is None:
            break
        streak += 1
    return streak
