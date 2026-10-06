"""Calificación anónima del servicio."""

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, FetchedValue, ForeignKey, Integer, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ServiceRating(Base):
    __tablename__ = "service_rating"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    appointment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("appointment.id"))
    site_id: Mapped[int] = mapped_column(Integer, ForeignKey("site.id"))
    service_date: Mapped[date] = mapped_column(Date)
    doctor_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("doctor.id"))
    token_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    score: Mapped[int | None] = mapped_column(SmallInteger)
    wait_score: Mapped[int | None] = mapped_column(SmallInteger)
    comment: Mapped[str | None] = mapped_column(String(500))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=FetchedValue())
