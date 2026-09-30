"""Modelos de trabajadores, dependencias y cobertura EPS."""

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Computed, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import FetchedValue

from app.core.db import Base, CreatedAtMixin, TimestampMixin
from app.modules.sites.models import Site


class Department(TimestampMixin, Base):
    __tablename__ = "department"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str | None] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(200))
    normalized_name: Mapped[str] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Insurer(CreatedAtMixin, Base):
    __tablename__ = "insurer"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class WorkerCoverage(TimestampMixin, Base):
    __tablename__ = "worker_coverage"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    worker_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("worker.id"))
    insurer_id: Mapped[int] = mapped_column(Integer, ForeignKey("insurer.id"))
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    end_reason: Mapped[str | None] = mapped_column(String(200))
    source_import_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("import_batch.id"))
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    updated_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))

    insurer: Mapped[Insurer] = relationship(lazy="joined")

    def covers(self, day: date) -> bool:
        return self.valid_from <= day and (self.valid_to is None or day <= self.valid_to)


class Worker(TimestampMixin, Base):
    __tablename__ = "worker"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    public_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), server_default=FetchedValue())
    document_type: Mapped[str] = mapped_column(String(3), default="DNI")
    document_number: Mapped[str] = mapped_column(String(12))
    first_names: Mapped[str] = mapped_column(String(100))
    paternal_surname: Mapped[str] = mapped_column(String(80))
    maternal_surname: Mapped[str | None] = mapped_column(String(80))
    birth_date: Mapped[date | None] = mapped_column(Date)
    sex: Mapped[str | None] = mapped_column(String(1))
    institutional_email: Mapped[str | None] = mapped_column(String(254))
    phone: Mapped[str | None] = mapped_column(String(20))
    employee_code: Mapped[str | None] = mapped_column(String(20))
    department_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("department.id"))
    work_site_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("site.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deactivation_reason: Mapped[str | None] = mapped_column(String(200))
    source_import_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("import_batch.id"))
    search_name: Mapped[str] = mapped_column(
        Text, Computed("upper(paternal_surname || ' ' || coalesce(maternal_surname, '') || ' ' || first_names)")
    )
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    updated_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))

    department: Mapped[Department | None] = relationship(lazy="joined")
    work_site: Mapped[Site | None] = relationship(lazy="joined")
    coverages: Mapped[list[WorkerCoverage]] = relationship(lazy="selectin", order_by="WorkerCoverage.valid_from.desc()")

    def coverage_on(self, day: date, insurer_code: str) -> WorkerCoverage | None:
        return next((c for c in self.coverages if c.insurer.code == insurer_code and c.covers(day)), None)

    def age_on(self, day: date) -> int | None:
        if self.birth_date is None:
            return None
        b = self.birth_date
        return day.year - b.year - ((day.month, day.day) < (b.month, b.day))
