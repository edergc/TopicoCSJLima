"""Canales de envío. Fase 1: correo (SMTP). Otros canales implementarían el mismo protocolo."""

import smtplib
import ssl
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path
from typing import Protocol

from app.core.config import Settings
from app.core.logging import get_logger

log = get_logger("app.notifications")


@dataclass(frozen=True)
class OutgoingMessage:
    notification_id: int
    recipient: str
    subject: str
    body_text: str
    body_html: str | None = None


class DeliveryError(Exception):
    """Error de envío; `permanent` indica que reintentar no tiene sentido."""

    def __init__(self, message: str, *, permanent: bool = False) -> None:
        super().__init__(message)
        self.permanent = permanent


class Channel(Protocol):
    def send(self, message: OutgoingMessage) -> None: ...


def _build_email(message: OutgoingMessage, sender: str) -> EmailMessage:
    email = EmailMessage()
    email["From"] = sender
    email["To"] = message.recipient
    email["Subject"] = message.subject
    email["Date"] = formatdate(localtime=False)
    email["Message-ID"] = make_msgid(domain=sender.split("@")[-1].strip(">") if "@" in sender else None)
    email["Auto-Submitted"] = "auto-generated"
    email.set_content(message.body_text)
    if message.body_html:
        email.add_alternative(message.body_html, subtype="html")
    return email


class SmtpEmailChannel:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def send(self, message: OutgoingMessage) -> None:
        s = self.settings
        assert s.smtp_host
        assert s.smtp_from
        email = _build_email(message, s.smtp_from)
        try:
            if s.smtp_security == "ssl":
                client: smtplib.SMTP = smtplib.SMTP_SSL(
                    s.smtp_host, s.smtp_port, timeout=s.smtp_timeout_seconds, context=ssl.create_default_context()
                )
            else:
                client = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=s.smtp_timeout_seconds)
            with client:
                if s.smtp_security == "starttls":
                    client.starttls(context=ssl.create_default_context())
                if s.smtp_username and s.smtp_password:
                    client.login(s.smtp_username, s.smtp_password.get_secret_value())
                client.send_message(email)
        except smtplib.SMTPRecipientsRefused as exc:
            raise DeliveryError(f"Destinatario rechazado: {exc.recipients}", permanent=True) from exc
        except smtplib.SMTPAuthenticationError as exc:
            raise DeliveryError("Autenticación SMTP fallida") from exc
        except (smtplib.SMTPException, OSError) as exc:
            raise DeliveryError(f"{type(exc).__name__}: {exc}") from exc


class ConsoleEmailChannel:
    """Desarrollo: registra el correo en el log técnico en lugar de enviarlo."""

    def send(self, message: OutgoingMessage) -> None:
        log.info("email_console", to=message.recipient, subject=message.subject, body=message.body_text)


class FileEmailChannel:
    """Desarrollo/pruebas: guarda cada correo como archivo .eml."""

    def __init__(self, directory: Path, sender: str) -> None:
        self.directory = directory
        self.sender = sender

    def send(self, message: OutgoingMessage) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        path = self.directory / f"{stamp}_{message.notification_id}.eml"
        path.write_bytes(bytes(_build_email(message, self.sender)))


def build_channel(settings: Settings) -> Channel | None:
    match settings.email_backend:
        case "smtp":
            return SmtpEmailChannel(settings)
        case "console":
            return ConsoleEmailChannel()
        case "file":
            return FileEmailChannel(settings.email_file_dir, settings.smtp_from or "topico@localhost")
        case _:
            return None
