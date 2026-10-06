"""Operación: pausa, cierre del día, panel en vivo y mensajes de la pantalla de sala."""

from datetime import date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response
from pydantic import Field, StringConstraints, model_validator

from app.modules.auth.dependencies import ServiceContext, require
from app.modules.operations import service as ops
from app.modules.sites.models import DisplayMessage, SitePause
from app.shared.schemas import ApiModel, ApiOut

router = APIRouter(tags=["Operación"])

OperateCtx = Annotated[ServiceContext, Depends(require("appointment:operate"))]
ConfigureCtx = Annotated[ServiceContext, Depends(require("site:configure"))]


# ------------------------------------------------------------------ pausa
class PauseIn(ApiModel):
    reason: Annotated[str, StringConstraints(min_length=3, max_length=150)]
    minutes: int = Field(ge=5, le=240, description="Duración prevista; se muestra la hora de reanudación.")


class PauseOut(ApiOut):
    id: int
    site_id: int
    started_at: datetime
    resume_at: datetime
    reason: str


@router.post("/sites/{site_id}/pause", response_model=PauseOut, status_code=201, summary="Pausar la atención")
def pause(site_id: int, body: PauseIn, ctx: OperateCtx) -> SitePause:
    return ops.pause_site(ctx, site_id, body.reason, body.minutes)


@router.post("/sites/{site_id}/resume", status_code=204, summary="Reanudar la atención")
def resume(site_id: int, ctx: OperateCtx) -> Response:
    ops.resume_site(ctx, site_id)
    return Response(status_code=204)


# ------------------------------------------------------------------ cierre del día
class DayCloseOut(ApiOut):
    service_date: date
    marked_no_show: int
    attended: int
    no_show: int
    cancelled: int
    summary_sent_to: int


@router.post(
    "/sites/{site_id}/service-days/{service_date}/close",
    response_model=DayCloseOut,
    summary="Cerrar el día: pendientes → no presentado y resumen PDF por correo",
)
def close_day(
    site_id: int, service_date: date, ctx: Annotated[ServiceContext, Depends(require("service_day:close"))]
) -> dict[str, Any]:
    return ops.close_day(ctx, site_id, service_date)


# ------------------------------------------------------------------ panel en vivo
class LiveCountsOut(ApiOut):
    capacity: int
    occupied: int
    available: int
    waiting: int
    called: int
    in_service: int
    attended: int
    no_show: int
    cancelled: int


class LiveInServiceOut(ApiOut):
    ticket_code: str
    doctor_name: str | None
    room_name: str | None
    started_at: datetime | None


class LivePauseOut(ApiOut):
    reason: str
    resume_at: datetime


class LiveIncidentOut(ApiOut):
    code: str
    message: str


class LiveSiteOut(ApiOut):
    site_id: int
    site_code: str
    site_name: str
    day_status: str | None
    counts: LiveCountsOut
    longest_wait_minutes: int | None
    avg_wait_minutes: float | None
    in_service: list[LiveInServiceOut]
    next_ticket_code: str | None
    pause: LivePauseOut | None
    incidents: list[LiveIncidentOut]


class LiveBoardOut(ApiOut):
    generated_at: datetime
    sites: list[LiveSiteOut]


@router.get("/dashboard/live", response_model=LiveBoardOut, summary="Panel en vivo de todas mis sedes")
def live(ctx: Annotated[ServiceContext, Depends(require("queue:read"))]) -> dict[str, Any]:
    return {"generated_at": ctx.clock.now(), "sites": ops.live_board(ctx)}


# ------------------------------------------------------------------ mensajes de sala
class DisplayMessageIn(ApiModel):
    site_id: int | None = Field(default=None, description="Vacío = todas las sedes (requiere site:manage).")
    text: Annotated[str, StringConstraints(min_length=3, max_length=200)]
    valid_from: date
    valid_to: date | None = None
    sort_order: int = Field(default=0, ge=0, le=999)

    @model_validator(mode="after")
    def _check_range(self) -> "DisplayMessageIn":
        if self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("La fecha final no puede ser anterior a la inicial.")
        return self


class DisplayMessageUpdateIn(ApiModel):
    text: Annotated[str, StringConstraints(min_length=3, max_length=200)] | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    sort_order: int | None = Field(default=None, ge=0, le=999)
    is_active: bool | None = None


class DisplayMessageOut(ApiOut):
    id: int
    site_id: int | None
    text: str
    valid_from: date
    valid_to: date | None
    sort_order: int
    is_active: bool
    updated_at: datetime


@router.get("/display-messages", response_model=list[DisplayMessageOut], summary="Mensajes de la pantalla de sala")
def list_messages(
    ctx: Annotated[ServiceContext, Depends(require("site:read"))], site_id: int | None = None
) -> list[DisplayMessage]:
    return ops.list_messages(ctx, site_id)


@router.post("/display-messages", response_model=DisplayMessageOut, status_code=201, summary="Crear mensaje")
def create_message(body: DisplayMessageIn, ctx: ConfigureCtx) -> DisplayMessage:
    return ops.create_message(ctx, body.model_dump())


@router.patch("/display-messages/{message_id}", response_model=DisplayMessageOut, summary="Modificar o desactivar")
def update_message(message_id: int, body: DisplayMessageUpdateIn, ctx: ConfigureCtx) -> DisplayMessage:
    return ops.update_message(ctx, message_id, body.model_dump(exclude_unset=True))
