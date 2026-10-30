"""Calificación anónima del servicio (2.6).

- Al finalizar una atención se crea una invitación con un token aleatorio; solo se guarda su SHA-256.
- El trabajador califica trato (1–5) y tiempo de espera (1–5), con comentario opcional.
- Los reportes solo muestran agregados y comentarios sin identificar a nadie.
"""

import hashlib
import secrets
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import BusinessRuleError, NotFoundError
from app.modules.admin.parameters import get_bool, get_int
from app.modules.appointments.models import Appointment
from app.modules.notifications import service as notifications
from app.modules.ratings.models import ServiceRating
from app.modules.sites.models import Doctor, Site

TEMPLATE = "RATING_REQUEST"


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def public_base_url(settings: Settings) -> str | None:
    url = (settings.public_app_url or "").rstrip("/")
    return url.removesuffix("/consulta") or None


def invite(
    db: Session,
    appointment: Appointment,
    clock: Clock,
    settings: Settings,
    *,
    notifications_enabled: bool,
    created_by: int | None,
) -> None:
    """Crea la invitación y encola el correo (solo si está habilitado y el trabajador tiene correo)."""
    base = public_base_url(settings)
    if not base or not get_bool(db, "rating.enabled", True) or not appointment.worker.institutional_email:
        return
    if db.scalar(select(ServiceRating.id).where(ServiceRating.appointment_id == appointment.id)):
        return
    days = max(get_int(db, "rating.valid_days", 7), 1)
    token = secrets.token_urlsafe(24)
    now = clock.now()
    db.add(
        ServiceRating(
            appointment_id=appointment.id,
            site_id=appointment.site_id,
            service_date=appointment.service_date,
            doctor_id=appointment.doctor_id,
            token_hash=_hash(token),
            expires_at=now + timedelta(days=days),
        )
    )
    db.flush()
    context = notifications.build_context(db, appointment, clock, settings) | {
        "rating_url": f"{base}/calificar#{token}",
        "rating_valid_days": days,
    }
    notifications.enqueue(
        db,
        template_code=TEMPLATE,
        appointment=appointment,
        context=context,
        now=now,
        notifications_enabled=notifications_enabled,
        created_by=created_by,
        dedup_key=f"{TEMPLATE}:{appointment.id}",
    )


def _by_token(db: Session, token: str) -> ServiceRating:
    rating = db.scalar(select(ServiceRating).where(ServiceRating.token_hash == _hash(token.strip())))
    if rating is None:
        raise NotFoundError("RATING_NOT_FOUND")
    return rating


def lookup(db: Session, token: str, now: datetime) -> dict[str, Any]:
    rating = _by_token(db, token)
    site = db.get(Site, rating.site_id)
    return {
        "site_name": site.name if site else "",
        "service_date": rating.service_date,
        "submitted": rating.submitted_at is not None,
        "expired": now >= rating.expires_at,
    }


def submit(db: Session, token: str, *, score: int, wait_score: int | None, comment: str | None, now: datetime) -> None:
    rating = _by_token(db, token)
    if rating.submitted_at is not None:
        raise BusinessRuleError("RATING_ALREADY_SUBMITTED")
    if now >= rating.expires_at:
        raise BusinessRuleError("RATING_EXPIRED")
    rating.score = score
    rating.wait_score = wait_score
    rating.comment = (comment or "").strip() or None
    rating.submitted_at = now
    db.commit()


def summary(
    db: Session, site_ids: list[int], date_from: date, date_to: date, *, include_comments: bool = False
) -> dict[str, Any]:
    """Resumen para Reportes. Los comentarios solo se incluyen con el permiso rating:read (jefatura)."""
    base = (
        ServiceRating.site_id.in_(site_ids),
        ServiceRating.service_date.between(date_from, date_to),
        ServiceRating.submitted_at.is_not(None),
    )
    count, avg_score, avg_wait = db.execute(
        select(func.count(), func.avg(ServiceRating.score), func.avg(ServiceRating.wait_score)).where(*base)
    ).one()
    invited = db.scalar(
        select(func.count()).where(
            ServiceRating.site_id.in_(site_ids), ServiceRating.service_date.between(date_from, date_to)
        )
    )
    distribution = dict(
        db.execute(select(ServiceRating.score, func.count()).where(*base).group_by(ServiceRating.score)).tuples().all()
    )
    comments = (
        []
        if not include_comments
        else db.execute(
            select(ServiceRating.service_date, Site.short_name, ServiceRating.score, ServiceRating.comment)
            .join(Site, Site.id == ServiceRating.site_id)
            .where(*base, ServiceRating.comment.is_not(None))
            .order_by(ServiceRating.submitted_at.desc())
            .limit(20)
        ).all()
    )
    return {
        "invited": invited or 0,
        "count": count,
        "avg_score": round(float(avg_score), 2) if avg_score is not None else None,
        "avg_wait_score": round(float(avg_wait), 2) if avg_wait is not None else None,
        "distribution": [{"score": s, "count": distribution.get(s, 0)} for s in range(1, 6)],
        "comments": [
            {"service_date": d, "site_name": site, "score": score, "comment": comment}
            for d, site, score, comment in comments
        ],
    }


# ------------------------------------------------------------------ reporte de satisfacción (rating:read)
MAX_EXPORT_COMMENTS = 5000


def _avg(value: Any) -> float | None:
    return round(float(value), 2) if value is not None else None


def report(
    db: Session,
    site_ids: list[int],
    date_from: date,
    date_to: date,
    *,
    doctor_id: int | None = None,
    score: int | None = None,
    page: int = 1,
    page_size: int = 25,
) -> dict[str, Any]:
    """Satisfacción del periodo: indicadores, evolución por mes, por sede y médico, y comentarios.

    El filtro de médico se aplica a todo; el de nota (estrellas de trato) solo a la lista de comentarios.
    Nada identifica al trabajador: la calificación no guarda su DNI ni su nombre.
    """
    scope: list[ColumnElement[bool]] = [
        ServiceRating.site_id.in_(site_ids),
        ServiceRating.service_date.between(date_from, date_to),
    ]
    if doctor_id is not None:
        scope.append(ServiceRating.doctor_id == doctor_id)
    answered = [*scope, ServiceRating.submitted_at.is_not(None)]
    stats = (func.count(), func.avg(ServiceRating.score), func.avg(ServiceRating.wait_score))

    invited = db.scalar(select(func.count()).where(*scope)) or 0
    count, avg_score, avg_wait = db.execute(select(*stats).where(*answered)).one()
    with_comment = db.scalar(select(func.count()).where(*answered, ServiceRating.comment.is_not(None))) or 0

    def buckets(column: Any) -> list[dict[str, int]]:
        found = dict(db.execute(select(column, func.count()).where(*answered).group_by(column)).tuples().all())
        return [{"score": s, "count": found.get(s, 0)} for s in range(1, 6)]

    month = func.to_char(ServiceRating.service_date, "YYYY-MM")
    by_month = db.execute(select(month, *stats).where(*answered).group_by(month).order_by(month)).all()
    by_site = db.execute(
        select(Site.short_name, *stats)
        .join(Site, Site.id == ServiceRating.site_id)
        .where(*answered)
        .group_by(Site.id, Site.short_name)
        .order_by(Site.id)
    ).all()
    by_doctor = db.execute(
        select(func.coalesce(Doctor.full_name, "Sin médico asignado"), *stats)
        .outerjoin(Doctor, Doctor.id == ServiceRating.doctor_id)
        .where(*answered)
        .group_by(Doctor.full_name)
        .order_by(func.count().desc())
    ).all()

    comment_filter: list[ColumnElement[bool]] = [*answered, ServiceRating.comment.is_not(None)]
    if score is not None:
        comment_filter.append(ServiceRating.score == score)
    comments_total = db.scalar(select(func.count()).where(*comment_filter)) or 0
    comments = db.execute(
        select(
            ServiceRating.service_date,
            ServiceRating.submitted_at,
            Site.short_name,
            Doctor.full_name,
            ServiceRating.score,
            ServiceRating.wait_score,
            ServiceRating.comment,
        )
        .join(Site, Site.id == ServiceRating.site_id)
        .outerjoin(Doctor, Doctor.id == ServiceRating.doctor_id)
        .where(*comment_filter)
        .order_by(ServiceRating.submitted_at.desc(), ServiceRating.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    def group(rows: Any, key: str) -> list[dict[str, Any]]:
        return [{key: k, "count": c, "avg_score": _avg(a), "avg_wait_score": _avg(w)} for k, c, a, w in rows]

    return {
        "date_from": date_from,
        "date_to": date_to,
        "invited": invited,
        "count": count,
        "response_pct": round(100.0 * count / invited, 1) if invited else None,
        "with_comment": with_comment,
        "avg_score": _avg(avg_score),
        "avg_wait_score": _avg(avg_wait),
        "distribution": buckets(ServiceRating.score),
        "wait_distribution": buckets(ServiceRating.wait_score),
        "by_month": group(by_month, "month"),
        "by_site": group(by_site, "site_name"),
        "by_doctor": group(by_doctor, "doctor"),
        "comments_total": comments_total,
        "page": page,
        "page_size": page_size,
        "comments": [
            {
                "service_date": d,
                "submitted_at": sub,
                "site_name": site,
                "doctor": doc,
                "score": s,
                "wait_score": w,
                "comment": text,
            }
            for d, sub, site, doc, s, w, text in comments
        ],
    }
