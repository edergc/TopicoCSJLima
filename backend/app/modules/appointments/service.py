"""Casos de uso de atenciones: registro, transiciones de estado, llamar siguiente y consultas.

Cada caso de uso es UNA transacción: valida → bloquea → modifica → registra evento +
auditoría + notificación → confirma. La BD garantiza además capacidad, numeración y
transiciones válidas (última línea de defensa).
"""

import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.context import get_request_context
from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.modules.appointments import priority
from app.modules.appointments import queue as queue_view
from app.modules.appointments.models import Appointment, AppointmentEvent, Reason, ServiceDay
from app.modules.appointments.schemas import AppointmentCreateIn, TransitionIn
from app.modules.appointments.state_machine import (
    ACTION_PERMISSION,
    ACTION_REASON_TYPE,
    ACTIVE_STATUSES,
    Action,
    Status,
    target_status,
)
from app.modules.audit import service as audit
from app.modules.auth.dependencies import ServiceContext
from app.modules.notifications import service as notifications
from app.modules.ratings import service as ratings
from app.modules.sites import doctors as doctor_rules
from app.modules.sites import service as sites
from app.modules.sites.models import ConsultingRoom, Doctor, Site, SitePause, SiteSettingVersion
from app.modules.workers import service as workers

# Acciones que solo se ejecutan sobre la cola del día en curso.
_TODAY_ONLY = frozenset({Action.CALL, Action.REQUEUE, Action.START, Action.FINISH, Action.NO_SHOW})
# Acciones tras las cuales la cola avanza (se evalúa el aviso "su atención se aproxima").
_QUEUE_ADVANCES = frozenset({Action.CALL, Action.START, Action.FINISH, Action.NO_SHOW, Action.CANCEL, Action.VOID})
_BLOCKER_CONFLICTS = frozenset({"CAPACITY_REACHED", "SERVICE_DAY_CLOSED"})


class AppointmentService:
    def __init__(self, ctx: ServiceContext) -> None:
        self.ctx = ctx
        self.db: Session = ctx.db
        self.clock = ctx.clock

    # =================================================================== registro
    def register(self, data: AppointmentCreateIn) -> Appointment:
        ctx, db = self.ctx, self.db
        ctx.require_site(data.site_id, action="APPOINTMENT_REGISTER")
        site = sites.get_site(db, data.site_id)
        today = self.clock.today()
        day = data.service_date or today
        dni = workers.parse_dni(data.document_number)

        # 1. Trabajador habilitado (RN-01)
        eligibility = workers.check_eligibility(db, dni, day)
        if not eligibility.eligible or eligibility.worker is None:
            self._audit_rejected(site.id, dni, eligibility.code or "WORKER_NOT_ELIGIBLE")
            raise BusinessRuleError(eligibility.code or "WORKER_NOT_ELIGIBLE")
        worker = eligibility.worker

        # 2-4. Sede activa, fecha permitida, sin cierre, dentro del horario, con cupo
        blocker = sites.registration_blocker(db, site, day, self.clock)
        if blocker:
            self._audit_rejected(site.id, dni, blocker)
            raise (ConflictError if blocker in _BLOCKER_CONFLICTS else BusinessRuleError)(blocker)

        # 5. Una atención activa por trabajador y día; reglas de re-registro
        setting = sites.effective_setting(db, site.id, day)
        assert setting is not None  # garantizado por registration_blocker
        self._check_previous_appointments(worker.id, day, setting)

        origin_id = self._resolve_origin(data.origin_appointment_id, worker.id)
        priority_reason = self._priority_reason(data.priority_reason_id)

        # 6. Bloqueo del día operativo: serializa los registros concurrentes de la sede/fecha
        service_day = self._lock_service_day(site.id, day)
        if service_day.status != "OPEN":
            raise ConflictError("SERVICE_DAY_CLOSED")
        if service_day.occupied_count >= service_day.capacity:
            self._audit_rejected(site.id, dni, "CAPACITY_REACHED")
            raise ConflictError("CAPACITY_REACHED")

        # 7. Crear (la BD asigna turno, sede y fecha)
        now = self.clock.now()
        status = Status.EN_ESPERA if day == today else Status.REGISTRADO
        appointment = Appointment(
            service_day_id=service_day.id,
            worker_id=worker.id,
            status=status,
            channel=data.channel,
            admin_note=data.admin_note or None,
            origin_appointment_id=origin_id,
            registered_at=now,
            registered_by=ctx.user.id,
            queued_at=now if status == Status.EN_ESPERA else None,
            call_count=0,
            priority_reason_id=priority_reason.id if priority_reason else None,
            priority_set_at=now if priority_reason else None,
            priority_set_by=ctx.user.id if priority_reason else None,
        )
        db.add(appointment)
        db.flush()
        db.expire(service_day)

        self._add_event(appointment, "REGISTER", None, status, None, None, now)
        ctx.audit(
            action="APPOINTMENT_REGISTER",
            resource_type="appointment",
            resource_id=appointment.public_id,
            site_id=site.id,
            after={
                "ticket_code": appointment.ticket_code,
                "status": status,
                "channel": data.channel,
                "service_date": day,
                "worker": str(worker.public_id),
                "origin_appointment_id": origin_id,
                "priority": priority_reason.code if priority_reason else None,
            },
        )

        # 8. Notificación (se envía después del commit, vía outbox)
        snapshot = queue_view.build_snapshot(db, site, day, self.clock)
        item = snapshot.item_for(appointment.id)
        notifications.enqueue(
            db,
            template_code=notifications.REGISTERED,
            appointment=appointment,
            context=notifications.build_context(
                db,
                appointment,
                self.clock,
                ctx.settings,
                people_ahead=item.people_ahead if item else None,
                estimated_time=item.estimated_at if item else None,
            ),
            now=now,
            notifications_enabled=setting.notifications_enabled,
            created_by=ctx.user.id,
            dedup_key=f"{notifications.REGISTERED}:{appointment.id}",
        )
        db.commit()
        return appointment

    # ============================================================== transiciones
    def transition(self, public_id: uuid.UUID, action: Action, data: TransitionIn) -> Appointment:
        appointment = self._load_for_update(public_id)
        self.ctx.require_site(appointment.site_id, action=f"APPOINTMENT_{action}")
        self.ctx.require_permission(ACTION_PERMISSION[action], action=f"APPOINTMENT_{action}")
        if data.version is not None and data.version != appointment.version:
            raise ConflictError("APPOINTMENT_CHANGED", details={"current_version": appointment.version})
        return self._apply(appointment, action, data)

    def call_next(self, site_id: int, room_id: int | None = None) -> Appointment:
        """LLAMAR SIGUIENTE: el menor turno EN_ESPERA del día (RN-11). SKIP LOCKED evita doble llamado."""
        self.ctx.require_site(site_id, action="APPOINTMENT_CALL_NEXT")
        service_day = sites.get_service_day(self.db, site_id, self.clock.today())
        if service_day is None:
            raise BusinessRuleError("QUEUE_EMPTY")
        next_id = self._next_in_line(service_day.id)
        if next_id is None:
            raise BusinessRuleError("QUEUE_EMPTY")
        appointment = self.db.scalar(
            select(Appointment).where(Appointment.id == next_id).with_for_update(of=Appointment, key_share=True)
        )
        assert appointment is not None
        return self._apply(appointment, Action.CALL, TransitionIn(room_id=room_id))

    def _apply(self, appointment: Appointment, action: Action, data: TransitionIn) -> Appointment:
        ctx, db = self.ctx, self.db
        current = appointment.status
        target = target_status(current, action)
        if target is None:
            raise ConflictError("INVALID_TRANSITION", details={"status": current, "action": action.value})

        today = self.clock.today()
        if action in _TODAY_ONLY and appointment.service_date != today:
            raise BusinessRuleError("NOT_TODAY")
        if appointment.service_date < today:
            raise BusinessRuleError("NOT_TODAY")

        reason = self._validate_reason(action, data)
        now = self.clock.now()
        service_day = appointment.service_day

        match action:
            case Action.CALL:
                pause = self.db.scalar(
                    select(SitePause).where(SitePause.site_id == appointment.site_id, SitePause.ended_at.is_(None))
                )
                if pause is not None:  # llamar a alguien termina la pausa
                    pause.ended_at, pause.ended_by = max(now, pause.started_at), ctx.user.id
                    ctx.audit(
                        action="SITE_RESUME",
                        resource_type="site",
                        resource_id=appointment.site_id,
                        site_id=appointment.site_id,
                        after={"automatic": True},
                    )
                room_id = self._resolve_room(appointment.site_id, data.room_id)
                appointment.room = self.db.get(ConsultingRoom, room_id) if room_id else None
                appointment.called_at, appointment.called_by = now, ctx.user.id
                appointment.call_count += 1
            case Action.REQUEUE:
                appointment.queued_at = now
            case Action.START:
                self._check_concurrent_in_service(service_day)
                doctor_id = self._resolve_doctor(appointment.site_id, data.doctor_id)
                appointment.doctor = self.db.get(Doctor, doctor_id) if doctor_id else None
                appointment.started_at, appointment.started_by = now, ctx.user.id
            case Action.FINISH:
                appointment.finished_at, appointment.finished_by = now, ctx.user.id
            case Action.NO_SHOW:
                expires = (appointment.called_at or now) + timedelta(minutes=service_day.tolerance_minutes)
                if now < expires:
                    raise BusinessRuleError(
                        "TOLERANCE_NOT_ELAPSED",
                        details={
                            "tolerance_expires_at": expires.isoformat(),
                            "seconds_remaining": int((expires - now).total_seconds()),
                        },
                    )
            case Action.CANCEL | Action.VOID:
                pass
        if action in (Action.CANCEL, Action.NO_SHOW, Action.VOID):
            appointment.closed_at, appointment.closed_by = now, ctx.user.id
            appointment.close_reason = reason
            appointment.close_note = data.note or None

        appointment.status = target
        db.flush()  # control de versión optimista + triggers (cupo, transición válida)
        db.expire(service_day)

        self._add_event(appointment, action.value, current, target, reason, data.note, now)
        ctx.audit(
            action=f"APPOINTMENT_{action.value}",
            resource_type="appointment",
            resource_id=appointment.public_id,
            site_id=appointment.site_id,
            reason=reason.label if reason else None,
            before={"status": current},
            after={
                "status": target,
                "ticket_code": appointment.ticket_code,
                "note": data.note,
                **({"doctor_id": appointment.doctor_id} if action == Action.START else {}),
                **({"room_id": appointment.room_id} if action == Action.CALL else {}),
            },
        )
        self._notify_after(appointment, action, reason, now)
        db.commit()
        return appointment

    def _next_in_line(self, service_day_id: int) -> int | None:
        """Siguiente EN_ESPERA: orden de registro o, con prioridad habilitada, la regla de prioridad.

        SKIP LOCKED evita que dos encargadas llamen a la misma persona.
        """
        if not priority.enabled(self.db):
            return self.db.scalar(
                select(Appointment.id)
                .where(Appointment.service_day_id == service_day_id, Appointment.status == Status.EN_ESPERA)
                .order_by(Appointment.ticket_number)
                .limit(1)
                .with_for_update(skip_locked=True, key_share=True)
            )
        waiting = self.db.execute(
            select(Appointment.id, Appointment.priority_reason_id)
            .where(Appointment.service_day_id == service_day_id, Appointment.status == Status.EN_ESPERA)
            .order_by(Appointment.ticket_number)
        ).all()
        limit = priority.max_consecutive(self.db)
        ordered = priority.call_order(
            waiting,
            lambda row: row.priority_reason_id is not None,
            priority.current_streak(self.db, service_day_id, limit),
            limit,
        )
        for row in ordered:
            locked = self.db.scalar(
                select(Appointment.id)
                .where(Appointment.id == row.id, Appointment.status == Status.EN_ESPERA)
                .with_for_update(skip_locked=True, key_share=True)
            )
            if locked is not None:
                return locked
        return None

    def _priority_reason(self, reason_id: int | None) -> Reason | None:
        if reason_id is None:
            return None
        if not priority.enabled(self.db):
            raise BusinessRuleError("PRIORITY_DISABLED")
        reason = self.db.get(Reason, reason_id)
        if reason is None or reason.type != "PRIORITY" or not reason.is_active:
            raise BusinessRuleError("PRIORITY_INVALID")
        return reason

    def set_priority(self, public_id: uuid.UUID, reason_id: int | None) -> Appointment:
        """Asigna o retira la prioridad de quien aún espera (auditado y en la línea de tiempo)."""
        appointment = self._load_for_update(public_id)
        self.ctx.require_site(appointment.site_id, action="APPOINTMENT_PRIORITY")
        if appointment.status not in (Status.REGISTRADO, Status.EN_ESPERA):
            raise ConflictError("INVALID_TRANSITION", details={"status": appointment.status, "action": "PRIORITY"})
        reason = self._priority_reason(reason_id) if reason_id is not None else None
        before = appointment.priority_reason.code if appointment.priority_reason else None
        now = self.clock.now()
        appointment.priority_reason = reason
        appointment.priority_set_at = now if reason else None
        appointment.priority_set_by = self.ctx.user.id if reason else None
        self.db.flush()
        note = f"Prioridad: {reason.label}" if reason else "Se retiró la prioridad"
        self._add_event(appointment, "PRIORITY", appointment.status, appointment.status, reason, note, now)
        self.ctx.audit(
            action="APPOINTMENT_PRIORITY",
            resource_type="appointment",
            resource_id=appointment.public_id,
            site_id=appointment.site_id,
            before={"priority": before},
            after={"priority": reason.code if reason else None, "ticket_code": appointment.ticket_code},
        )
        self.db.commit()
        return appointment

    def _resolve_room(self, site_id: int, room_id: int | None) -> int | None:
        """Consultorio del llamado: el indicado, o el único activo de la sede. Sin consultorios → None."""
        active = list(
            self.db.scalars(
                select(ConsultingRoom.id).where(ConsultingRoom.site_id == site_id, ConsultingRoom.is_active)
            )
        )
        if room_id is not None:
            if room_id not in active:
                raise BusinessRuleError("ROOM_INVALID")
            return room_id
        if len(active) > 1:
            raise BusinessRuleError("ROOM_REQUIRED")
        return active[0] if active else None

    def _resolve_doctor(self, site_id: int, doctor_id: int | None) -> int | None:
        """Médico que atiende: el indicado (presente hoy) o, si no se indica, el único de turno.

        De turno = activo, sin ausencia y dentro de su horario (sin horario: todo el horario de la sede).
        Si nadie está de turno en este momento, se consideran los presentes del día.
        """
        present, on_duty = doctor_rules.assignable(self.db, site_id, self.clock.today(), self.clock.local_now())
        if doctor_id is not None:
            if doctor_id not in {d.id for d in present}:
                raise BusinessRuleError("DOCTOR_INVALID")
            return doctor_id
        pool = on_duty or present
        if len(pool) > 1:
            raise BusinessRuleError("DOCTOR_REQUIRED")
        return pool[0].id if pool else None

    # ================================================================ consultas
    def get(self, public_id: uuid.UUID) -> Appointment:
        appointment = self.db.scalar(select(Appointment).where(Appointment.public_id == public_id))
        if appointment is None:
            raise NotFoundError("APPOINTMENT_NOT_FOUND")
        self.ctx.require_site(appointment.site_id, action="APPOINTMENT_READ")
        return appointment

    def events(self, public_id: uuid.UUID) -> list[AppointmentEvent]:
        appointment = self.get(public_id)
        return list(
            self.db.scalars(
                select(AppointmentEvent)
                .where(AppointmentEvent.appointment_id == appointment.id)
                .order_by(AppointmentEvent.occurred_at, AppointmentEvent.id)
            )
        )

    def search(
        self,
        *,
        site_id: int | None,
        date_from: date | None,
        date_to: date | None,
        status: str | None,
        document_number: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[Appointment], int]:
        if site_id is not None:
            self.ctx.require_site(site_id, action="APPOINTMENT_SEARCH")
            site_ids: list[int] = [site_id]
        else:
            site_ids = sorted(self.ctx.user.site_ids)
        stmt = select(Appointment).where(Appointment.site_id.in_(site_ids))
        if date_from:
            stmt = stmt.where(Appointment.service_date >= date_from)
        if date_to:
            stmt = stmt.where(Appointment.service_date <= date_to)
        if status:
            stmt = stmt.where(Appointment.status == status)
        if document_number:
            worker = workers.find_by_document(self.db, workers.parse_dni(document_number))
            stmt = stmt.where(Appointment.worker_id == (worker.id if worker else -1))
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = self.db.scalars(
            stmt.order_by(Appointment.service_date.desc(), Appointment.site_id, Appointment.ticket_number)
            .offset(offset)
            .limit(limit)
        ).unique()
        return list(rows), int(total)

    # ================================================================ internos
    def _lock_service_day(self, site_id: int, day: date) -> ServiceDay:
        day_id = self.db.scalar(text("SELECT topico.ensure_service_day(:s, :d)"), {"s": site_id, "d": day})
        service_day = self.db.scalar(
            select(ServiceDay)
            .where(ServiceDay.id == day_id)
            .with_for_update(key_share=True)
            .execution_options(populate_existing=True)
        )
        assert service_day is not None
        fresh = service_day.occupied_count == 0 and service_day.capacity_adjusted_at is None
        if fresh and sites.apply_planned_capacity(self.db, service_day, self.clock.now(), self.ctx.user.id):
            self.db.flush()
        return service_day

    def _load_for_update(self, public_id: uuid.UUID) -> Appointment:
        appointment = self.db.scalar(
            select(Appointment)
            .where(Appointment.public_id == public_id)
            .with_for_update(of=Appointment, key_share=True)
            .execution_options(populate_existing=True)
        )
        if appointment is None:
            raise NotFoundError("APPOINTMENT_NOT_FOUND")
        return appointment

    def _check_previous_appointments(self, worker_id: int, day: date, setting: SiteSettingVersion) -> None:
        previous = list(
            self.db.scalars(
                select(Appointment).where(Appointment.worker_id == worker_id, Appointment.service_date == day)
            ).unique()
        )
        active = next((a for a in previous if a.status in ACTIVE_STATUSES), None)
        if active is not None:
            raise ConflictError(
                "WORKER_ALREADY_HAS_APPOINTMENT",
                f"El trabajador ya tiene el turno {active.ticket_code} ({active.site.short_name}) para esa fecha.",
                details={"ticket_code": active.ticket_code, "public_id": str(active.public_id)},
            )
        statuses = {a.status for a in previous}
        if Status.NO_PRESENTADO in statuses and not setting.allow_reregister_after_no_show:
            raise BusinessRuleError("REREGISTER_NOT_ALLOWED")
        if Status.CANCELADO in statuses and not setting.allow_reregister_after_cancel:
            raise BusinessRuleError("REREGISTER_NOT_ALLOWED")

    def _resolve_origin(self, origin_public_id: uuid.UUID | None, worker_id: int) -> int | None:
        if origin_public_id is None:
            return None
        origin = self.db.scalar(select(Appointment).where(Appointment.public_id == origin_public_id))
        if origin is None or origin.worker_id != worker_id:
            raise BusinessRuleError("VALIDATION_ERROR", "La atención de origen no corresponde al trabajador.")
        return origin.id

    def _validate_reason(self, action: Action, data: TransitionIn) -> Reason | None:
        reason_type = ACTION_REASON_TYPE.get(action)
        if reason_type is None:
            return None
        if data.reason_id is None:
            if action is Action.NO_SHOW:  # motivo por defecto: "No acudió tras ser llamado"
                return self.db.scalar(
                    select(Reason)
                    .where(Reason.type == "NO_SHOW", Reason.is_active)
                    .order_by(Reason.sort_order)
                    .limit(1)
                )
            if action is Action.REQUEUE:
                return None
            raise BusinessRuleError("REASON_REQUIRED")
        reason = self.db.get(Reason, data.reason_id)
        if reason is None or reason.type != reason_type or not reason.is_active:
            raise BusinessRuleError("REASON_INVALID")
        if reason.requires_note and not (data.note and data.note.strip()):
            raise BusinessRuleError("NOTE_REQUIRED")
        return reason

    def _check_concurrent_in_service(self, service_day: ServiceDay) -> None:
        locked = self.db.scalar(
            select(ServiceDay)
            .where(ServiceDay.id == service_day.id)
            .with_for_update(key_share=True)
            .execution_options(populate_existing=True)
        )
        assert locked is not None
        in_service = self.db.scalar(
            select(func.count())
            .select_from(Appointment)
            .where(Appointment.service_day_id == service_day.id, Appointment.status == Status.EN_ATENCION)
        )
        if (in_service or 0) >= locked.max_concurrent_in_service:
            raise ConflictError("MAX_IN_SERVICE_REACHED")

    def _add_event(
        self,
        appointment: Appointment,
        action: str,
        from_status: str | None,
        to_status: str,
        reason: Reason | None,
        note: str | None,
        now: datetime,
        *,
        system: bool = False,
    ) -> None:
        req = get_request_context()
        self.db.add(
            AppointmentEvent(
                appointment_id=appointment.id,
                action=action,
                from_status=from_status,
                to_status=to_status,
                reason_id=reason.id if reason else None,
                note=note or None,
                occurred_at=now,
                user_id=None if system else self.ctx.user.id,
                ip=req.ip,
                request_id=req.request_id,
            )
        )

    def _audit_rejected(self, site_id: int, dni: str, code: str) -> None:
        """Deja trazabilidad de intentos de registro rechazados (p. ej., trabajador no habilitado)."""
        audit.record_isolated(
            self.ctx.session_factory,
            action="APPOINTMENT_REGISTER",
            actor=self.ctx.user,
            result="FAILURE",
            resource_type="worker_document",
            resource_id=dni,
            site_id=site_id,
            reason=code,
        )

    def _notify_after(self, appointment: Appointment, action: Action, reason: Reason | None, now: datetime) -> None:
        setting = sites.effective_setting(self.db, appointment.site_id, appointment.service_date)
        enabled = setting.notifications_enabled if setting else False
        if action is Action.CALL:
            notifications.enqueue(
                self.db,
                template_code=notifications.CALLED,
                appointment=appointment,
                context=notifications.build_context(self.db, appointment, self.clock, self.ctx.settings),
                now=now,
                notifications_enabled=enabled,
                created_by=self.ctx.user.id,
                dedup_key=f"{notifications.CALLED}:{appointment.id}:{appointment.call_count}",
            )
        elif action is Action.CANCEL:
            notifications.enqueue(
                self.db,
                template_code=notifications.CANCELLED,
                appointment=appointment,
                context=notifications.build_context(
                    self.db, appointment, self.clock, self.ctx.settings, reason_label=reason.label if reason else None
                ),
                now=now,
                notifications_enabled=enabled,
                created_by=self.ctx.user.id,
                dedup_key=f"{notifications.CANCELLED}:{appointment.id}",
            )
        elif action is Action.FINISH:
            ratings.invite(
                self.db,
                appointment,
                self.clock,
                self.ctx.settings,
                notifications_enabled=enabled,
                created_by=self.ctx.user.id,
            )
        if action in _QUEUE_ADVANCES and setting is not None and setting.upcoming_notice_ahead > 0:
            self._notify_upcoming(appointment.site, appointment.service_date, setting, now)

    def _notify_upcoming(self, site: Site, day: date, setting: SiteSettingVersion, now: datetime) -> None:
        snapshot = queue_view.build_snapshot(self.db, site, day, self.clock)
        for item in snapshot.waiting:
            if item.people_ahead is None or item.people_ahead > setting.upcoming_notice_ahead:
                break
            notifications.enqueue(
                self.db,
                template_code=notifications.UPCOMING,
                appointment=item.appointment,
                context=notifications.build_context(
                    self.db,
                    item.appointment,
                    self.clock,
                    self.ctx.settings,
                    people_ahead=item.people_ahead,
                    estimated_time=item.estimated_at,
                ),
                now=now,
                notifications_enabled=setting.notifications_enabled,
                created_by=None,
                dedup_key=f"{notifications.UPCOMING}:{item.appointment.id}",
            )
