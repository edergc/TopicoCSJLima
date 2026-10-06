"""Procesos en segundo plano (hilo dentro del proceso; sin colas externas).

1. Despacho de la bandeja de salida (outbox) con reintentos y backoff exponencial.
2. Mantenimiento: activa las atenciones REGISTRADO cuyo día llegó (REGISTRADO → EN_ESPERA).

Es seguro con varios workers de Uvicorn: los registros se reclaman con FOR UPDATE SKIP LOCKED.
"""

import threading
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import Clock
from app.core.config import Settings
from app.core.logging import get_logger
from app.modules.admin.parameters import get_int
from app.modules.appointments.models import Appointment, AppointmentEvent
from app.modules.appointments.state_machine import Status
from app.modules.audit import service as audit
from app.modules.notifications.channels import Channel, DeliveryError, OutgoingMessage, build_channel
from app.modules.notifications.models import Notification

log = get_logger("app.notifications")

BATCH_SIZE = 20
STALE_SENDING = timedelta(minutes=10)


class NotificationDispatcher:
    def __init__(
        self, session_factory: sessionmaker[Session], settings: Settings, clock: Clock, channel: Channel | None = None
    ) -> None:
        self.factory = session_factory
        self.settings = settings
        self.clock = clock
        self.channel = channel if channel is not None else build_channel(settings)

    def process_batch(self) -> int:
        """Envía hasta BATCH_SIZE notificaciones pendientes. Devuelve cuántas procesó."""
        if self.channel is None:
            return 0
        now = self.clock.now()
        with self.factory() as db:
            # Recupera envíos interrumpidos (p. ej., reinicio del servidor durante el envío).
            db.execute(
                update(Notification)
                .where(Notification.status == "SENDING", Notification.updated_at < now - STALE_SENDING)
                .values(status="PENDING")
            )
            claimed = list(
                db.scalars(
                    select(Notification)
                    .where(Notification.status == "PENDING", Notification.next_attempt_at <= now)
                    .order_by(Notification.next_attempt_at, Notification.id)
                    .limit(BATCH_SIZE)
                    .with_for_update(skip_locked=True, key_share=True)
                )
            )
            for n in claimed:
                n.status = "SENDING"
            db.commit()
            messages = [
                OutgoingMessage(
                    n.id,
                    n.recipient or "",
                    n.subject or "",
                    n.body_text or "",
                    n.body_html,
                    (n.attachment_name, n.attachment_type or "application/octet-stream", n.attachment_data)
                    if n.attachment_name and n.attachment_data
                    else None,
                )
                for n in claimed
            ]

        for message in messages:
            self._deliver(message)
        return len(messages)

    def _deliver(self, message: OutgoingMessage) -> None:
        assert self.channel is not None
        error: DeliveryError | None = None
        try:
            self.channel.send(message)
        except DeliveryError as exc:
            error = exc
        except Exception as exc:  # cualquier fallo inesperado del canal se trata como reintentable
            error = DeliveryError(f"{type(exc).__name__}: {exc}")

        now = self.clock.now()
        with self.factory() as db:
            n = db.get(Notification, message.notification_id, with_for_update={"key_share": True})
            if n is None:
                return
            n.attempts += 1
            if error is None:
                n.status, n.sent_at, n.last_error = "SENT", now, None
                log.info("notification_sent", notification_id=n.id, template=n.template_code)
            else:
                n.last_error = str(error)[:1000]
                if error.permanent or n.attempts >= n.max_attempts:
                    n.status = "FAILED"
                    log.error("notification_failed", notification_id=n.id, error=n.last_error, attempts=n.attempts)
                else:
                    base = get_int(db, "notification.retry_base_seconds", 60)
                    n.status = "PENDING"
                    n.next_attempt_at = now + timedelta(seconds=base * 2 ** (n.attempts - 1))
                    log.warning("notification_retry", notification_id=n.id, error=n.last_error, attempts=n.attempts)
            db.commit()


def activate_due_appointments(session_factory: sessionmaker[Session], clock: Clock) -> int:
    """REGISTRADO → EN_ESPERA para las atenciones cuya fecha ya llegó (acción del sistema)."""
    today = clock.today()
    now = clock.now()
    with session_factory() as db:
        due = list(
            db.scalars(
                select(Appointment)
                .where(Appointment.status == Status.REGISTRADO, Appointment.service_date <= today)
                .order_by(Appointment.service_day_id, Appointment.ticket_number)
                .limit(200)
                .with_for_update(of=Appointment, skip_locked=True, key_share=True)
            ).unique()
        )
        for appt in due:
            appt.status = Status.EN_ESPERA
            appt.queued_at = now
            db.add(
                AppointmentEvent(
                    appointment_id=appt.id,
                    action="ACTIVATE",
                    from_status=Status.REGISTRADO,
                    to_status=Status.EN_ESPERA,
                    occurred_at=now,
                )
            )
            audit.record(
                db,
                action="APPOINTMENT_ACTIVATE",
                username="sistema",
                resource_type="appointment",
                resource_id=appt.public_id,
                site_id=appt.site_id,
                before={"status": Status.REGISTRADO},
                after={"status": Status.EN_ESPERA},
            )
        db.commit()
        return len(due)


class BackgroundDispatcher:
    """Hilo de fondo que ejecuta periódicamente el despacho y el mantenimiento."""

    def __init__(self, session_factory: sessionmaker[Session], settings: Settings, clock: Clock) -> None:
        self.dispatcher = NotificationDispatcher(session_factory, settings, clock)
        self.factory = session_factory
        self.clock = clock
        self.interval = settings.notifications_poll_seconds
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="topico-background", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=10)

    def _run(self) -> None:
        log.info("background_worker_started", interval_seconds=self.interval)
        while not self._stop.is_set():
            try:
                activate_due_appointments(self.factory, self.clock)
                while self.dispatcher.process_batch() == BATCH_SIZE and not self._stop.is_set():
                    pass
            except Exception:
                log.exception("background_worker_error")
            self._stop.wait(self.interval)
        log.info("background_worker_stopped")
