"""Modelos de la agenda diaria y de las atenciones."""

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, FetchedValue, ForeignKey, Integer, SmallInteger, String
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, TimestampMixin
from app.modules.sites.models import ConsultingRoom, Doctor, Site
from app.modules.workers.models import Worker


class Reason(TimestampMixin, Base):
    __tablename__ = "reason"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(15))
    code: Mapped[str] = mapped_column(String(40))
    label: Mapped[str] = mapped_column(String(150))
    requires_note: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0)
    updated_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))


class AppointmentStatus(Base):
    __tablename__ = "appointment_status"

    code: Mapped[str] = mapped_column(String(15), primary_key=True)
    label: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(String(200))
    consumes_capacity: Mapped[bool] = mapped_column(Boolean)
    is_final: Mapped[bool] = mapped_column(Boolean)
    is_active_queue: Mapped[bool] = mapped_column(Boolean)
    sort_order: Mapped[int] = mapped_column(SmallInteger)


class AppointmentStatusTransition(Base):
    __tablename__ = "appointment_status_transition"

    from_status: Mapped[str] = mapped_column(String(15), ForeignKey("appointment_status.code"), primary_key=True)
    to_status: Mapped[str] = mapped_column(String(15), ForeignKey("appointment_status.code"), primary_key=True)
    action: Mapped[str] = mapped_column(String(20))


class ServiceDay(TimestampMixin, Base):
    __tablename__ = "service_day"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    site_id: Mapped[int] = mapped_column(Integer, ForeignKey("site.id"))
    service_date: Mapped[date] = mapped_column(Date)
    setting_version_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("site_setting_version.id"))
    status: Mapped[str] = mapped_column(String(6))
    capacity: Mapped[int] = mapped_column(SmallInteger)
    slot_minutes: Mapped[int] = mapped_column(SmallInteger)
    tolerance_minutes: Mapped[int] = mapped_column(SmallInteger)
    max_concurrent_in_service: Mapped[int] = mapped_column(SmallInteger)
    occupied_count: Mapped[int] = mapped_column(SmallInteger)
    last_ticket_number: Mapped[int] = mapped_column(SmallInteger)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    capacity_adjusted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    capacity_adjusted_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    capacity_adjust_reason: Mapped[str | None] = mapped_column(String(300))

    @property
    def available(self) -> int:
        return max(self.capacity - self.occupied_count, 0)


class Appointment(TimestampMixin, Base):
    __tablename__ = "appointment"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    public_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), server_default=FetchedValue())
    service_day_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("service_day.id"))
    # Asignados por el trigger de la BD al insertar:
    site_id: Mapped[int] = mapped_column(Integer, ForeignKey("site.id"), server_default=FetchedValue())
    service_date: Mapped[date] = mapped_column(Date, server_default=FetchedValue())
    ticket_number: Mapped[int] = mapped_column(SmallInteger, server_default=FetchedValue())
    ticket_code: Mapped[str] = mapped_column(String(8), server_default=FetchedValue())
    worker_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("worker.id"))
    status: Mapped[str] = mapped_column(String(15), ForeignKey("appointment_status.code"))
    channel: Mapped[str] = mapped_column(String(10))
    origin_appointment_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("appointment.id"))
    admin_note: Mapped[str | None] = mapped_column(String(300))
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    registered_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=FetchedValue())
    called_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    called_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    call_count: Mapped[int] = mapped_column(SmallInteger, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    close_reason_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("reason.id"))
    close_note: Mapped[str | None] = mapped_column(String(300))
    doctor_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("doctor.id"))
    room_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("consulting_room.id"))
    priority_reason_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("reason.id"))
    priority_set_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    priority_set_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    version: Mapped[int] = mapped_column(Integer)

    worker: Mapped[Worker] = relationship(lazy="joined", innerjoin=True)
    site: Mapped[Site] = relationship(lazy="joined", innerjoin=True)
    service_day: Mapped[ServiceDay] = relationship(lazy="joined", innerjoin=True)
    close_reason: Mapped[Reason | None] = relationship(lazy="joined", foreign_keys=[close_reason_id])
    priority_reason: Mapped[Reason | None] = relationship(lazy="joined", foreign_keys=[priority_reason_id])
    doctor: Mapped[Doctor | None] = relationship(lazy="joined")
    room: Mapped[ConsultingRoom | None] = relationship(lazy="joined")

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class AppointmentEvent(Base):
    __tablename__ = "appointment_event"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    appointment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("appointment.id"))
    action: Mapped[str] = mapped_column(String(20))
    from_status: Mapped[str | None] = mapped_column(String(15))
    to_status: Mapped[str] = mapped_column(String(15))
    reason_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("reason.id"))
    note: Mapped[str | None] = mapped_column(String(300))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    ip: Mapped[str | None] = mapped_column(INET)
    request_id: Mapped[str | None] = mapped_column(String(40))

    reason: Mapped[Reason | None] = relationship(lazy="joined")
