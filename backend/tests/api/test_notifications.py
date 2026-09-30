"""Outbox de notificaciones: despacho, reintentos, fallos permanentes e integración SMTP real."""

import socket
from collections.abc import Callable, Iterator

import pytest
from aiosmtpd.controller import Controller
from aiosmtpd.handlers import Message
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.clock import FixedClock
from app.core.config import Settings
from app.modules.notifications.channels import DeliveryError, OutgoingMessage, SmtpEmailChannel
from app.modules.notifications.models import Notification
from app.modules.notifications.worker import NotificationDispatcher

from .conftest import Actor, api, register, site_id


class RecordingChannel:
    def __init__(self, fail_with: DeliveryError | None = None) -> None:
        self.sent: list[OutgoingMessage] = []
        self.fail_with = fail_with

    def send(self, message: OutgoingMessage) -> None:
        if self.fail_with:
            raise self.fail_with
        self.sent.append(message)


@pytest.fixture(autouse=True)
def isolate_outbox(app: FastAPI) -> None:
    """Cada prueba procesa solo sus propias notificaciones."""
    with app.state.session_factory() as s:
        s.execute(update(Notification).where(Notification.status == "PENDING").values(status="CANCELLED"))
        s.commit()


def _dispatcher(app: FastAPI, settings: Settings, clock: FixedClock, channel: object) -> NotificationDispatcher:
    return NotificationDispatcher(app.state.session_factory, settings, clock, channel)  # type: ignore[arg-type]


def test_registration_email_is_rendered_and_sent(
    app: FastAPI,
    test_settings: Settings,
    client: TestClient,
    operator: Actor,
    make_worker: Callable[..., str],
    db: Session,
    clock: FixedClock,
) -> None:
    appt = register(client, operator, site_id(db), make_worker()).json()
    channel = RecordingChannel()
    assert _dispatcher(app, test_settings, clock, channel).process_batch() == 1
    [message] = channel.sent
    assert message.recipient == "trabajador@pj.gob.pe"
    assert appt["ticket_code"] in message.subject
    assert "Estimado(a) Ana:" in message.body_text
    assert "Sede Javier Alzamora Valdez" in message.body_text
    sent = db.scalar(select(Notification).where(Notification.id == message.notification_id))
    assert sent is not None
    assert (sent.status, sent.attempts) == ("SENT", 1)


def test_worker_without_email_is_skipped(
    client: TestClient, operator: Actor, make_worker: Callable[..., str], db: Session
) -> None:
    appt = register(client, operator, site_id(db), make_worker(email=None)).json()
    [note] = client.get(api(f"/appointments/{appt['public_id']}/notifications"), headers=operator.headers).json()
    assert (note["status"], note["last_error"]) == ("SKIPPED", "El trabajador no tiene correo registrado.")


def test_transient_failures_retry_with_backoff_then_fail(
    app: FastAPI,
    test_settings: Settings,
    client: TestClient,
    operator: Actor,
    make_worker: Callable[..., str],
    db: Session,
    clock: FixedClock,
) -> None:
    register(client, operator, site_id(db), make_worker())
    failing = _dispatcher(app, test_settings, clock, RecordingChannel(DeliveryError("SMTP caído")))
    assert failing.process_batch() == 1
    note = db.scalar(select(Notification).order_by(Notification.id.desc()).limit(1))
    assert note is not None
    db.refresh(note)
    assert (note.status, note.attempts, note.last_error) == ("PENDING", 1, "SMTP caído")
    assert failing.process_batch() == 0  # aún no toca reintentar (backoff)

    for _ in range(4):
        clock.advance(hours=1)
        failing.process_batch()
    db.refresh(note)
    assert (note.status, note.attempts) == ("FAILED", 5)


def test_permanent_failure_is_not_retried(
    app: FastAPI,
    test_settings: Settings,
    client: TestClient,
    operator: Actor,
    make_worker: Callable[..., str],
    db: Session,
    clock: FixedClock,
) -> None:
    register(client, operator, site_id(db), make_worker())
    _dispatcher(
        app, test_settings, clock, RecordingChannel(DeliveryError("Buzón inexistente", permanent=True))
    ).process_batch()
    note = db.scalar(select(Notification).order_by(Notification.id.desc()).limit(1))
    assert note is not None
    assert (note.status, note.attempts) == ("FAILED", 1)


def test_resend_creates_new_pending_notification(
    client: TestClient, operator: Actor, make_worker: Callable[..., str], db: Session
) -> None:
    appt = register(client, operator, site_id(db), make_worker()).json()
    [note] = client.get(api(f"/appointments/{appt['public_id']}/notifications"), headers=operator.headers).json()
    resent = client.post(api(f"/notifications/{note['id']}/resend"), headers=operator.headers)
    assert (resent.status_code, resent.json()["status"]) == (201, "PENDING")


def test_upcoming_notice_when_queue_advances(
    client: TestClient, operator: Actor, make_worker: Callable[..., str], db: Session
) -> None:
    alz = site_id(db)
    appts = [register(client, operator, alz, make_worker()).json() for _ in range(4)]
    client.post(api(f"/sites/{alz}/queue/call-next"), headers=operator.headers)  # llama A-001
    upcoming = {
        a["ticket_code"]
        for a in appts
        for n in client.get(api(f"/appointments/{a['public_id']}/notifications"), headers=operator.headers).json()
        if n["template_code"] == "APPT_UPCOMING"
    }
    # Con upcoming_notice_ahead = 2: quienes tienen <= 2 personas delante (contando al llamado).
    assert upcoming == {"A-002", "A-003"}


# ------------------------------------------------------------------ SMTP real


class _Handler(Message):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[object] = []

    def handle_message(self, message: object) -> None:
        self.messages.append(message)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture
def smtp_server() -> Iterator[tuple[_Handler, int]]:
    handler = _Handler()
    port = _free_port()
    controller = Controller(handler, hostname="127.0.0.1", port=port)
    controller.start()
    try:
        yield handler, port
    finally:
        controller.stop()


def test_smtp_channel_delivers_utf8_email(test_settings: Settings, smtp_server: tuple[_Handler, int]) -> None:
    handler, port = smtp_server
    settings = test_settings.model_copy(
        update={
            "email_backend": "smtp",
            "smtp_host": "127.0.0.1",
            "smtp_port": port,
            "smtp_security": "none",
            "smtp_from": "Tópico CSJ Lima <topico@pj.gob.pe>",
        }
    )
    SmtpEmailChannel(settings).send(
        OutgoingMessage(1, "ana@pj.gob.pe", "Su atención se aproxima — A-007", "Acérquese al tópico.")
    )
    [message] = handler.messages
    assert message["To"] == "ana@pj.gob.pe"  # type: ignore[index]
    assert "A-007" in str(message["Subject"])  # type: ignore[index]


def test_smtp_connection_error_is_transient(test_settings: Settings) -> None:
    settings = test_settings.model_copy(
        update={
            "email_backend": "smtp",
            "smtp_host": "127.0.0.1",
            "smtp_port": _free_port(),
            "smtp_security": "none",
            "smtp_from": "topico@pj.gob.pe",
            "smtp_timeout_seconds": 2,
        }
    )
    with pytest.raises(DeliveryError) as exc:
        SmtpEmailChannel(settings).send(OutgoingMessage(1, "ana@pj.gob.pe", "x", "y"))
    assert exc.value.permanent is False
