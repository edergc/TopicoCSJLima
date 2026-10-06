from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select

from app.core.errors import MESSAGES
from app.modules.auth.dependencies import ServiceContext, require
from app.modules.sites import doctors as doctor_rules
from app.modules.sites import service as sites
from app.modules.sites.config_service import SiteConfigService
from app.modules.sites.models import ConsultingRoom, DoctorAbsence, DoctorSchedule, Site, SiteClosure
from app.modules.sites.schemas import (
    AbsenceIn,
    AbsenceOut,
    AvailabilityOut,
    BlockOut,
    CapacityAdjustIn,
    ClosureIn,
    ClosureOut,
    DoctorBlock,
    DoctorIn,
    DoctorOut,
    DoctorScheduleIn,
    DoctorUpdateIn,
    RoomIn,
    RoomOut,
    RoomUpdateIn,
    ScheduleIn,
    ScheduleRowOut,
    SettingVersionIn,
    SettingVersionOut,
    SiteCreateIn,
    SiteOut,
    SiteSettingsOut,
    SiteUpdateIn,
)

router = APIRouter(prefix="/sites", tags=["Sedes"])

ReadCtx = Annotated[ServiceContext, Depends(require("site:read"))]
ConfigureCtx = Annotated[ServiceContext, Depends(require("site:configure"))]
ManageCtx = Annotated[ServiceContext, Depends(require("site:manage"))]


@router.get("", response_model=list[SiteOut], summary="Sedes autorizadas para el usuario")
def list_sites(ctx: ReadCtx) -> list[Site]:
    return list(ctx.db.scalars(select(Site).where(Site.id.in_(ctx.user.site_ids)).order_by(Site.id)))


@router.get("/all", response_model=list[SiteOut], summary="Todas las sedes, incluidas las inactivas (administración)")
def list_all_sites(ctx: ManageCtx) -> list[Site]:
    return list(ctx.db.scalars(select(Site).order_by(Site.id)))


@router.post("", response_model=SiteOut, status_code=201, summary="Crear una sede nueva (con configuración y horario)")
def create_site(body: SiteCreateIn, ctx: ManageCtx) -> Site:
    return SiteConfigService(ctx).create_site(body)


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


def _doctors_out(ctx: ServiceContext, site_id: int, only: list[int] | None = None) -> list[DoctorOut]:
    today = ctx.clock.today()
    local_now = ctx.clock.local_now()
    days = {d.doctor.id: d for d in doctor_rules.doctors_for_day(ctx.db, site_id, today)}
    ids = [i for i in days if only is None or i in only]
    schedule: dict[int, list[DoctorBlock]] = {i: [] for i in ids}
    for row in ctx.db.scalars(
        select(DoctorSchedule)
        .where(DoctorSchedule.doctor_id.in_(ids))
        .order_by(DoctorSchedule.weekday, DoctorSchedule.start_time)
    ):
        schedule[row.doctor_id].append(
            DoctorBlock(weekday=row.weekday, start_time=row.start_time, end_time=row.end_time)
        )
    absences: dict[int, list[AbsenceOut]] = {i: [] for i in ids}
    for a in ctx.db.scalars(
        select(DoctorAbsence)
        .where(DoctorAbsence.doctor_id.in_(ids), DoctorAbsence.date_to >= today)
        .order_by(DoctorAbsence.date_from)
    ):
        absences[a.doctor_id].append(AbsenceOut.model_validate(a))
    out = []
    for i in ids:
        day = days[i]
        out.append(
            DoctorOut.model_validate(day.doctor).model_copy(
                update={
                    "schedule": schedule[i],
                    "present_today": day.present,
                    "on_duty_now": day.on_duty_at(local_now.time()),
                    "absence_reason": day.absence_reason,
                    "upcoming_absences": absences[i],
                }
            )
        )
    out.sort(key=lambda d: (not d.is_active, d.full_name))
    return out


@router.get(
    "/{site_id}/doctors", response_model=list[DoctorOut], summary="Médicos de la sede, con horario y disponibilidad"
)
def list_doctors(site_id: int, ctx: ReadCtx, active_only: bool = False) -> list[DoctorOut]:
    ctx.require_site(site_id, action="DOCTOR_READ")
    doctors = _doctors_out(ctx, site_id)
    return [d for d in doctors if d.is_active] if active_only else doctors


@router.post("/{site_id}/doctors", response_model=DoctorOut, status_code=201, summary="Registrar médico")
def create_doctor(site_id: int, body: DoctorIn, ctx: ConfigureCtx) -> DoctorOut:
    doctor = SiteConfigService(ctx).create_doctor(site_id, body)
    return _doctors_out(ctx, site_id, [doctor.id])[0]


@router.patch("/{site_id}/doctors/{doctor_id}", response_model=DoctorOut, summary="Modificar o desactivar médico")
def update_doctor(site_id: int, doctor_id: int, body: DoctorUpdateIn, ctx: ConfigureCtx) -> DoctorOut:
    SiteConfigService(ctx).update_doctor(site_id, doctor_id, body)
    return _doctors_out(ctx, site_id, [doctor_id])[0]


@router.put(
    "/{site_id}/doctors/{doctor_id}/schedule", response_model=DoctorOut, summary="Reemplazar el horario del médico"
)
def replace_doctor_schedule(site_id: int, doctor_id: int, body: DoctorScheduleIn, ctx: ConfigureCtx) -> DoctorOut:
    SiteConfigService(ctx).replace_doctor_schedule(site_id, doctor_id, body)
    return _doctors_out(ctx, site_id, [doctor_id])[0]


@router.post(
    "/{site_id}/doctors/{doctor_id}/absences", response_model=DoctorOut, status_code=201, summary="Registrar ausencia"
)
def add_absence(site_id: int, doctor_id: int, body: AbsenceIn, ctx: ConfigureCtx) -> DoctorOut:
    SiteConfigService(ctx).add_absence(site_id, doctor_id, body)
    return _doctors_out(ctx, site_id, [doctor_id])[0]


@router.delete(
    "/{site_id}/doctors/{doctor_id}/absences/{absence_id}", response_model=DoctorOut, summary="Eliminar ausencia"
)
def remove_absence(site_id: int, doctor_id: int, absence_id: int, ctx: ConfigureCtx) -> DoctorOut:
    SiteConfigService(ctx).remove_absence(site_id, doctor_id, absence_id)
    return _doctors_out(ctx, site_id, [doctor_id])[0]


@router.get("/{site_id}/rooms", response_model=list[RoomOut], summary="Consultorios del tópico de la sede")
def list_rooms(site_id: int, ctx: ReadCtx, active_only: bool = False) -> list[ConsultingRoom]:
    ctx.require_site(site_id, action="ROOM_READ")
    stmt = select(ConsultingRoom).where(ConsultingRoom.site_id == site_id)
    if active_only:
        stmt = stmt.where(ConsultingRoom.is_active)
    order = (ConsultingRoom.is_active.desc(), ConsultingRoom.sort_order, ConsultingRoom.name)
    return list(ctx.db.scalars(stmt.order_by(*order)))


@router.post("/{site_id}/rooms", response_model=RoomOut, status_code=201, summary="Registrar consultorio")
def create_room(site_id: int, body: RoomIn, ctx: ConfigureCtx) -> ConsultingRoom:
    return SiteConfigService(ctx).create_room(site_id, body)


@router.patch("/{site_id}/rooms/{room_id}", response_model=RoomOut, summary="Modificar o desactivar consultorio")
def update_room(site_id: int, room_id: int, body: RoomUpdateIn, ctx: ConfigureCtx) -> ConsultingRoom:
    return SiteConfigService(ctx).update_room(site_id, room_id, body)
