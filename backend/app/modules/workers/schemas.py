import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import EmailStr, Field, StringConstraints

from app.shared.schemas import ApiModel, ApiOut

Name = Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True, min_length=1, max_length=100)]
Surname = Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True, min_length=1, max_length=80)]
Phone = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^\+?[0-9 ]{6,20}$")]


class DepartmentOut(ApiOut):
    id: int
    code: str | None
    name: str


class CoverageOut(ApiOut):
    id: int
    insurer_code: str
    insurer_name: str
    valid_from: date
    valid_to: date | None
    end_reason: str | None


class WorkerSummaryOut(ApiOut):
    """Datos mínimos para la mesa de operación y listados."""

    public_id: uuid.UUID
    document_type: str
    document_number: str
    first_names: str
    paternal_surname: str
    maternal_surname: str | None
    department_name: str | None
    has_email: bool
    has_phone: bool
    is_active: bool


class WorkerOut(WorkerSummaryOut):
    """Ficha completa (lectura auditada)."""

    birth_date: date | None
    age: int | None
    sex: str | None
    institutional_email: str | None
    phone: str | None
    employee_code: str | None
    department_id: int | None
    work_site_id: int | None
    deactivated_at: datetime | None
    deactivation_reason: str | None
    coverages: list[CoverageOut]
    created_at: datetime
    updated_at: datetime


class TodayAppointmentOut(ApiOut):
    public_id: uuid.UUID
    ticket_code: str
    status: str
    site_id: int
    site_name: str
    service_date: date


class EligibilityOut(ApiOut):
    document_number: str
    found: bool
    eligible: bool
    code: str | None
    message: str
    worker: WorkerSummaryOut | None
    coverage: CoverageOut | None
    active_appointment: TodayAppointmentOut | None


class WorkerCreateIn(ApiModel):
    document_type: Literal["DNI"] = "DNI"
    document_number: Annotated[str, StringConstraints(min_length=5, max_length=12)]
    first_names: Name
    paternal_surname: Surname
    maternal_surname: Surname | None = None
    birth_date: date | None = None
    sex: Literal["F", "M"] | None = None
    institutional_email: EmailStr | None = None
    phone: Phone | None = None
    employee_code: Annotated[str, StringConstraints(max_length=20)] | None = None
    department_name: Annotated[str, StringConstraints(min_length=2, max_length=200)] | None = None
    work_site_id: int | None = None
    coverage_valid_from: date | None = Field(default=None, description="Si se indica, crea la cobertura EPS Rímac")


class WorkerUpdateIn(ApiModel):
    first_names: Name | None = None
    paternal_surname: Surname | None = None
    maternal_surname: Surname | None = None
    birth_date: date | None = None
    sex: Literal["F", "M"] | None = None
    institutional_email: EmailStr | None = None
    phone: Phone | None = None
    employee_code: Annotated[str, StringConstraints(max_length=20)] | None = None
    department_name: Annotated[str, StringConstraints(min_length=2, max_length=200)] | None = None
    work_site_id: int | None = None
    is_active: bool | None = None
    deactivation_reason: Annotated[str, StringConstraints(min_length=3, max_length=200)] | None = None


class CoverageIn(ApiModel):
    valid_from: date
    valid_to: date | None = None


class CoverageEndIn(ApiModel):
    valid_to: date
    end_reason: Annotated[str, StringConstraints(min_length=3, max_length=200)]
