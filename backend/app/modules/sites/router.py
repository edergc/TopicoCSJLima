from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select

from app.core.errors import MESSAGES
from app.modules.auth.dependencies import ServiceContext, require
from app.modules.sites import service as sites
from app.modules.sites.config_service import SiteConfigService
from app.modules.sites.models import Doctor, Site, SiteClosure
from app.modules.sites.schemas import (
    AvailabilityOut,
    BlockOut,
    CapacityAdjustIn,
    ClosureIn,
    ClosureOut,
    DoctorIn,
    DoctorOut,
    DoctorUpdateIn,
    ScheduleIn,
    ScheduleRowOut,
    SettingVersionIn,
    SettingVersionOut,
    SiteOut,
    SiteSettingsOut,
    SiteUpdateIn,
)

router = APIRouter(prefix="/sites", tags=["Sedes"])

ReadCtx = Annotated[ServiceContext, Depends(require("site:read"))]
ConfigureCtx = Annotated[ServiceContext, Depends(require("site:configure"))]


@router.get("", response_model=list[SiteOut], summary="Sedes autorizadas para el usuario")
def list_sites(ctx: ReadCtx) -> list[Site]:
    return list(ctx.db.scalars(select(Site).where(Site.id.in_(ctx.user.site_ids)).order_by(Site.id)))


@router.get("/{site_id}", response_model=SiteOut)
def get_site(site_id: int, ctx: ReadCtx) -> Site:
    ctx.require_site(site_id, action="SITE_READ")
    return sites.get_site(ctx.db, site_id)


@router.patch("/{site_id}", response_model=SiteOut, summary="Actualizar datos de la sede")
def update_site(site_id: int, body: SiteUpdateIn, ctx: ConfigureCtx) -> Site:
    return SiteConfigService(ctx).update_site(site_id, body)


@router.get("/{site_id}/availability", response_model=AvailabilityOut, summary="Capacidad y disponibilidad")
def availability(
    site_id: int, ctx: ReadCtx, date_: Annotated[date | None, Query(alias="date")] = None
) -> AvailabilityOut:
    ctx.require_site(site_id, action="SITE_AVAILABILITY")
    site = sites.get_site(ctx.db, site_id)
    a = sites.availability(ctx.db, site, date_ or ctx.clock.today(), ctx.clock)
    return AvailabilityOut(
        site_id=site.id,
        service_date=a.service_date,
        capacity=a.capacity,
        occupied=a.occupied,
        available=a.available,
        day_status=a.day_status,
        can_register=a.can_register,
        blocker_code=a.blocker,
        blocker_message=MESSAGES.get(a.blocker) if a.blocker else None,
        blocks=[BlockOut(block=b.block, start=b.start, end=b.end) for b in a.blocks],
        closure_reason=a.closure_reason,
    )


@router.get("/{site_id}/settings", response_model=SiteSettingsOut, summary="Configuración vigente e historial")
def get_settings(site_id: int, ctx: ReadCtx) -> SiteSettingsOut:
    ctx.require_site(site_id, action="SITE_SETTINGS_READ")
    sites.get_site(ctx.db, site_id)
    current = sites.effective_setting(ctx.db, site_id, ctx.clock.today())
    history = sites.setting_history(ctx.db, site_id)
    return SiteSettingsOut(
        current=SettingVersionOut.model_validate(current) if current else None,
        history=[SettingVersionOut.model_validate(h) for h in history],
    )


@router.post(
    "/{site_id}/settings",
    response_model=SettingVersionOut,
    status_code=201,
    summary="Programar nueva configuración (desde una fecha futura)",
)
def save_settings(site_id: int, body: SettingVersionIn, ctx: ConfigureCtx) -> SettingVersionOut:
    return SettingVersionOut.model_validate(SiteConfigService(ctx).save_setting_version(site_id, body))


@router.get("/{site_id}/schedules", response_model=list[ScheduleRowOut], summary="Horario vigente en una fecha")
def get_schedule(
    site_id: int, ctx: ReadCtx, date_: Annotated[date | None, Query(alias="date")] = None
) -> list[ScheduleRowOut]:
    ctx.require_site(site_id, action="SITE_SCHEDULE_READ")
    rows = sites.schedule_rows(ctx.db, site_id, date_ or ctx.clock.today())
    return [ScheduleRowOut.model_validate(r) for r in rows]


@router.put("/{site_id}/schedules", response_model=list[ScheduleRowOut], summary="Programar nuevo horario semanal")
def replace_schedule(site_id: int, body: ScheduleIn, ctx: ConfigureCtx) -> list[ScheduleRowOut]:
    return [ScheduleRowOut.model_validate(r) for r in SiteConfigService(ctx).replace_schedule(site_id, body)]


@router.get("/{site_id}/closures", response_model=list[ClosureOut], summary="Días sin atención")
def list_closures(
    site_id: int,
    ctx: ReadCtx,
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: Annotated[date | None, Query()] = None,
) -> list[ClosureOut]:
    ctx.require_site(site_id, action="SITE_CLOSURE_READ")
    stmt = select(SiteClosure).where(SiteClosure.site_id == site_id)
    stmt = stmt.where(SiteClosure.closure_date >= (from_ or ctx.clock.today()))
    if to:
        stmt = stmt.where(SiteClosure.closure_date <= to)
    return [ClosureOut.model_validate(c) for c in ctx.db.scalars(stmt.order_by(SiteClosure.closure_date))]


@router.post("/{site_id}/closures", response_model=ClosureOut, status_code=201)
def add_closure(site_id: int, body: ClosureIn, ctx: ConfigureCtx) -> ClosureOut:
    return ClosureOut.model_validate(SiteConfigService(ctx).add_closure(site_id, body))


@router.delete("/{site_id}/closures/{closure_id}", status_code=204)
def remove_closure(site_id: int, closure_id: int, ctx: ConfigureCtx) -> Response:
    SiteConfigService(ctx).remove_closure(site_id, closure_id)
    return Response(status_code=204)


@router.patch(
    "/{site_id}/service-days/{service_date}/capacity",
    response_model=AvailabilityOut,
    summary="Ajustar la capacidad de un día (auditado)",
)
def adjust_capacity(
    site_id: int,
    service_date: date,
    body: CapacityAdjustIn,
    ctx: Annotated[ServiceContext, Depends(require("service_day:adjust"))],
) -> AvailabilityOut:
    SiteConfigService(ctx).adjust_capacity(site_id, service_date, body)
    return availability(site_id, ctx, service_date)


@router.get("/{site_id}/doctors", response_model=list[DoctorOut], summary="Médicos del tópico de la sede")
def list_doctors(site_id: int, ctx: ReadCtx, active_only: bool = False) -> list[Doctor]:
    ctx.require_site(site_id, action="DOCTOR_READ")
    stmt = select(Doctor).where(Doctor.site_id == site_id)
    if active_only:
        stmt = stmt.where(Doctor.is_active)
    return list(ctx.db.scalars(stmt.order_by(Doctor.is_active.desc(), Doctor.full_name)))


@router.post("/{site_id}/doctors", response_model=DoctorOut, status_code=201, summary="Registrar médico")
def create_doctor(site_id: int, body: DoctorIn, ctx: ConfigureCtx) -> Doctor:
    return SiteConfigService(ctx).create_doctor(site_id, body)


@router.patch("/{site_id}/doctors/{doctor_id}", response_model=DoctorOut, summary="Modificar o desactivar médico")
def update_doctor(site_id: int, doctor_id: int, body: DoctorUpdateIn, ctx: ConfigureCtx) -> Doctor:
    return SiteConfigService(ctx).update_doctor(site_id, doctor_id, body)
