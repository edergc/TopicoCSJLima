from datetime import date, datetime, time
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from app.shared.schemas import ApiModel, ApiOut

Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=300)]


class SiteOut(ApiOut):
    id: int
    code: str
    name: str
    short_name: str
    ticket_prefix: str
    address: str | None
    location_note: str | None
    is_active: bool


class SiteUpdateIn(ApiModel):
    name: Annotated[str, StringConstraints(min_length=3, max_length=120)] | None = None
    short_name: Annotated[str, StringConstraints(min_length=2, max_length=40)] | None = None
    address: Annotated[str, StringConstraints(max_length=250)] | None = None
    location_note: Annotated[str, StringConstraints(max_length=250)] | None = None
    is_active: bool | None = None


class BlockOut(ApiOut):
    block: str
    start: time
    end: time


class AvailabilityOut(ApiOut):
    site_id: int
    service_date: date
    capacity: int
    occupied: int
    available: int
    day_status: str | None
    can_register: bool
    blocker_code: str | None
    blocker_message: str | None
    blocks: list[BlockOut]
    closure_reason: str | None


class SettingVersionOut(ApiOut):
    id: int
    valid_from: date
    daily_capacity: int
    slot_minutes: int
    tolerance_minutes: int
    max_concurrent_in_service: int
    registration_cutoff_minutes: int
    upcoming_notice_ahead: int
    allow_reregister_after_no_show: bool
    allow_reregister_after_cancel: bool
    notifications_enabled: bool
    change_reason: str | None
    created_at: datetime


class SiteSettingsOut(ApiOut):
    current: SettingVersionOut | None
    history: list[SettingVersionOut]


class SettingVersionIn(ApiModel):
    valid_from: date
    daily_capacity: int = Field(ge=1, le=500)
    slot_minutes: int = Field(ge=5, le=120)
    tolerance_minutes: int = Field(ge=0, le=120)
    max_concurrent_in_service: int = Field(default=1, ge=1, le=10)
    registration_cutoff_minutes: int = Field(default=0, ge=0, le=480)
    upcoming_notice_ahead: int = Field(default=2, ge=0, le=20)
    allow_reregister_after_no_show: bool = False
    allow_reregister_after_cancel: bool = True
    notifications_enabled: bool = True
    change_reason: Reason


class ScheduleBlockIn(ApiModel):
    weekday: int = Field(ge=1, le=7, description="1 = lunes … 7 = domingo")
    block: Literal["AM", "PM"]
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def _check_times(self) -> "ScheduleBlockIn":
        if self.end_time <= self.start_time:
            raise ValueError("La hora de fin debe ser posterior a la de inicio.")
        return self


class ScheduleIn(ApiModel):
    valid_from: date
    blocks: list[ScheduleBlockIn] = Field(min_length=1, max_length=14)
    change_reason: Reason


class ScheduleRowOut(ApiOut):
    id: int
    weekday: int
    block: str
    start_time: time
    end_time: time
    valid_from: date
    valid_to: date | None


class ClosureIn(ApiModel):
    closure_date: date
    reason: Annotated[str, StringConstraints(min_length=3, max_length=200)]


class ClosureOut(ApiOut):
    id: int
    closure_date: date
    reason: str
    created_at: datetime


class CapacityAdjustIn(ApiModel):
    capacity: int = Field(ge=0, le=500)
    reason: Reason


DoctorName = Annotated[str, StringConstraints(min_length=3, max_length=150)]
DoctorDni = Annotated[str, StringConstraints(pattern=r"^\d{8}$")]
DoctorCmp = Annotated[str, StringConstraints(pattern=r"^\d{1,6}$")]


class DoctorIn(ApiModel):
    full_name: DoctorName
    document_number: DoctorDni | None = None
    cmp: DoctorCmp | None = Field(default=None, description="N.° de colegiatura del Colegio Médico del Perú")
    specialty: Annotated[str, StringConstraints(max_length=80)] | None = None
    phone: Annotated[str, StringConstraints(max_length=20)] | None = None
    email: Annotated[str, StringConstraints(max_length=150, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")] | None = None


class DoctorUpdateIn(ApiModel):
    full_name: DoctorName | None = None
    document_number: DoctorDni | None = None
    cmp: DoctorCmp | None = None
    specialty: Annotated[str, StringConstraints(max_length=80)] | None = None
    phone: Annotated[str, StringConstraints(max_length=20)] | None = None
    email: Annotated[str, StringConstraints(max_length=150, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")] | None = None
    is_active: bool | None = None


class DoctorOut(ApiOut):
    id: int
    site_id: int
    full_name: str
    document_number: str | None
    cmp: str | None
    specialty: str | None
    phone: str | None
    email: str | None
    is_active: bool
    updated_at: datetime
