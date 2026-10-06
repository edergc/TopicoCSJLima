"""Modelos de notificaciones: plantillas y bandeja de salida (outbox)."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, LargeBinary, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin


class NotificationTemplate(TimestampMixin, Base):
    __tablename__ = "notification_template"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40))
    channel: Mapped[str] = mapped_column(String(10), default="EMAIL")
    description: Mapped[str] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(String(200))
    body_text: Mapped[str] = mapped_column(Text)
    body_html: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))


class Notification(TimestampMixin, Base):
    __tablename__ = "notification"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    appointment_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("appointment.id"))
    template_code: Mapped[str] = mapped_column(String(40))
    channel: Mapped[str] = mapped_column(String(10))
    recipient: Mapped[str | None] = mapped_column(String(254))
    subject: Mapped[str | None] = mapped_column(String(200))
    body_text: Mapped[str | None] = mapped_column(Text)
    body_html: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="PENDING")
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    max_attempts: Mapped[int] = mapped_column(SmallInteger, default=5)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(1000))
    dedup_key: Mapped[str | None] = mapped_column(String(120))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    attachment_name: Mapped[str | None] = mapped_column(String(150))
    attachment_type: Mapped[str | None] = mapped_column(String(80))
    attachment_data: Mapped[bytes | None] = mapped_column(LargeBinary)
