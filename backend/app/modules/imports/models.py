"""Modelos de importación de Excel (staging)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, FetchedValue, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, CreatedAtMixin, TimestampMixin


class ImportBatch(TimestampMixin, Base):
    __tablename__ = "import_batch"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    public_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), server_default=FetchedValue())
    kind: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(12), default="UPLOADED")
    file_name: Mapped[str] = mapped_column(String(255))
    file_sha256: Mapped[str] = mapped_column(String(64))
    file_size_bytes: Mapped[int] = mapped_column(Integer)
    sheet_name: Mapped[str | None] = mapped_column(String(100))
    options: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    column_mapping: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    new_count: Mapped[int] = mapped_column(Integer, default=0)
    update_count: Mapped[int] = mapped_column(Integer, default=0)
    unchanged_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    deactivated_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_message: Mapped[str | None] = mapped_column(String(1000))
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    discarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discarded_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))


class ImportRow(CreatedAtMixin, Base):
    __tablename__ = "import_row"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    batch_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("import_batch.id"))
    row_number: Mapped[int] = mapped_column(Integer)
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB)
    normalized: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    outcome: Mapped[str] = mapped_column(String(20))
    errors: Mapped[list[str]] = mapped_column(JSONB, default=list)
    warnings: Mapped[list[str]] = mapped_column(JSONB, default=list)
    changes: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    target_worker_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("worker.id"))
