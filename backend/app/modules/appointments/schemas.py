import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import Field

from app.shared.schemas import ApiModel, ApiOut, Note


class AppointmentCreateIn(ApiModel):
    site_id: int
    document_number: str = Field(min_length=5, max_length=12)
    channel: Literal["PHONE", "WALK_IN"]
    admin_note: Note | None = Field(
        default=None, description="Observación ADMINISTRATIVA. No registrar síntomas ni información clínica."
    )
    service_date: date | None = Field(default=None, description="Por defecto, hoy (America/Lima).")
    origin_appointment_id: uuid.UUID | None = Field(default=None, description="Atención original si es reprogramación")


class CallNextIn(ApiModel):
    room_id: int | None = Field(default=None, description="Consultorio al que se llama.")


class TransitionIn(ApiModel):
    version: int | None = Field(default=None, description="Versión esperada (control de concurrencia).")
    reason_id: int | None = None
    note: Note | None = None
    room_id: int | None = Field(
        default=None, description="Al LLAMAR: consultorio (obligatorio si la sede tiene más de uno activo)."
    )
    doctor_id: int | None = Field(
        default=None, description="Al INICIAR: médico que atiende (obligatorio si la sede tiene más de uno activo)."
    )


class WorkerBriefOut(ApiOut):
    public_id: uuid.UUID
    document_number: str
    display_name: str
    short_name: str
    department_name: str | None
    has_email: bool


class ReasonOut(ApiOut):
    id: int
    type: str
    code: str
    label: str
    requires_note: bool


class AppointmentOut(ApiOut):
    public_id: uuid.UUID
    ticket_code: str
    ticket_number: int
    status: str
    channel: str
    site_id: int
    site_name: str
    service_date: date
    worker: WorkerBriefOut
    registered_at: datetime
    queued_at: datetime | None
    called_at: datetime | None
    call_count: int
    started_at: datetime | None
    finished_at: datetime | None
    closed_at: datetime | None
    close_reason: ReasonOut | None
    close_note: str | None
    admin_note: str | None
    doctor_id: int | None = None
    doctor_name: str | None = None
    room_id: int | None = None
    room_name: str | None = None
    version: int
    allowed_actions: list[str]
    position: int | None = None
    people_ahead: int | None = None
    estimated_at: datetime | None = None
    tolerance_expires_at: datetime | None = None


class QueueCountsOut(ApiOut):
    capacity: int
    occupied: int
    available: int
    total: int
    registered: int
    waiting: int
    called: int
    in_service: int
    attended: int
    cancelled: int
    no_show: int
    voided: int


class IncidentOut(ApiOut):
    code: str
    message: str
    ticket_code: str | None


class QueueOut(ApiOut):
    site_id: int
    site_name: str
    service_date: date
    generated_at: datetime
    day_status: str | None
    next_ticket_code: str | None
    counts: QueueCountsOut
    in_service: list[AppointmentOut]
    called: list[AppointmentOut]
    waiting: list[AppointmentOut]
    registered: list[AppointmentOut]
    finished: list[AppointmentOut]
    closed: list[AppointmentOut]
    incidents: list[IncidentOut]


class AppointmentEventOut(ApiOut):
    action: str
    from_status: str | None
    to_status: str
    reason_label: str | None
    note: str | None
    occurred_at: datetime
    user_name: str | None


class NotificationOut(ApiOut):
    id: int
    template_code: str
    channel: str
    status: str
    recipient_masked: str | None
    subject: str | None
    attempts: int
    last_error: str | None
    sent_at: datetime | None
    created_at: datetime


class StatusOut(ApiOut):
    code: str
    label: str
    description: str
    consumes_capacity: bool
    is_final: bool
    sort_order: int
