"""Modelo de auditoría funcional (solo inserción; la BD calcula la cadena de hash)."""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, FetchedValue, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class AuditEvent(Base):
    __tablename__ = "audit_event"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chain_seq: Mapped[int] = mapped_column(BigInteger, server_default=FetchedValue())
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=FetchedValue())
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    username: Mapped[str | None] = mapped_column(String(50))
    ip: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(String(500))
    request_id: Mapped[str | None] = mapped_column(String(40))
    action: Mapped[str] = mapped_column(String(60))
    resource_type: Mapped[str | None] = mapped_column(String(40))
    resource_id: Mapped[str | None] = mapped_column(String(64))
    site_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("site.id"))
    result: Mapped[str] = mapped_column(String(10))
    reason: Mapped[str | None] = mapped_column(String(500))
    before_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB)
    prev_hash: Mapped[str | None] = mapped_column(String(64), server_default=FetchedValue())
    hash: Mapped[str] = mapped_column(String(64), server_default=FetchedValue())
