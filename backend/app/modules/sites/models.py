"""Modelos de sedes y su configuración operativa."""

from datetime import date, datetime, time

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    FetchedValue,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Time,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, CreatedAtMixin, TimestampMixin


class Site(TimestampMixin, Base):
    __tablename__ = "site"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(10))
    name: Mapped[str] = mapped_column(String(120))
    short_name: Mapped[str] = mapped_column(String(40))
    ticket_prefix: Mapped[str] = mapped_column(String(3))
    address: Mapped[str | None] = mapped_column(String(250))
    location_note: Mapped[str | None] = mapped_column(String(250))
    timezone: Mapped[str] = mapped_column(String(50), default="America/Lima")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger)
    updated_by: Mapped[int | None] = mapped_column(BigInteger)


class SiteSettingVersion(TimestampMixin, Base):
    __tablename__ = "site_setting_version"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    site_id: Mapped[int] = mapped_column(Integer, ForeignKey("site.id"))
    valid_from: Mapped[date] = mapped_column(Date)
    daily_capacity: Mapped[int] = mapped_column(SmallInteger)
    slot_minutes: Mapped[int] = mapped_column(SmallInteger)
    tolerance_minutes: Mapped[int] = mapped_column(SmallInteger)
    max_concurrent_in_service: Mapped[int] = mapped_column(SmallInteger, default=1)
    registration_cutoff_minutes: Mapped[int] = mapped_column(SmallInteger, default=0)
    upcoming_notice_ahead: Mapped[int] = mapped_column(SmallInteger, default=2)
    allow_reregister_after_no_show: Mapped[bool] = mapped_column(Boolean, default=False)
    allow_reregister_after_cancel: Mapped[bool] = mapped_column(Boolean, default=True)
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    change_reason: Mapped[str | None] = mapped_column(String(300))
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    updated_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))


class SiteSchedule(TimestampMixin, Base):
    __tablename__ = "site_schedule"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    site_id: Mapped[int] = mapped_column(Integer, ForeignKey("site.id"))
    weekday: Mapped[int] = mapped_column(SmallInteger)
    block: Mapped[str] = mapped_column(String(2))
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    updated_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))


class SiteClosure(CreatedAtMixin, Base):
    __tablename__ = "site_closure"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    site_id: Mapped[int] = mapped_column(Integer, ForeignKey("site.id"))
    closure_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(String(200))
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))


class SystemParameter(Base):
    __tablename__ = "system_parameter"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[object] = mapped_column(JSONB)
    value_type: Mapped[str] = mapped_column(String(10))
    description: Mapped[str] = mapped_column(String(300))
    is_editable: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=FetchedValue(), server_onupdate=FetchedValue()
    )
    updated_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))


class Doctor(TimestampMixin, Base):
    """Médico del tópico de una sede (solo datos administrativos del profesional)."""

    __tablename__ = "doctor"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_id: Mapped[int] = mapped_column(Integer, ForeignKey("site.id"))
    full_name: Mapped[str] = mapped_column(String(150))
    document_number: Mapped[str | None] = mapped_column(String(8))
    cmp: Mapped[str | None] = mapped_column(String(6))
    specialty: Mapped[str | None] = mapped_column(String(80))
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(150))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    updated_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))
