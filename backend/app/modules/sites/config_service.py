"""Casos de uso de configuración de sede (todos auditados)."""

from datetime import date, timedelta

from sqlalchemy import insert, select, text

from app.core.errors import BusinessRuleError, NotFoundError
from app.modules.appointments.models import ServiceDay
from app.modules.audit.service import diff, snapshot
from app.modules.auth.dependencies import ServiceContext
from app.modules.sites import service as sites
from app.modules.sites.models import (
    ConsultingRoom,
    Doctor,
    DoctorAbsence,
    DoctorSchedule,
    Site,
    SiteClosure,
    SiteSchedule,
    SiteSettingVersion,
)
from app.modules.sites.schemas import (
    AbsenceIn,
    CapacityAdjustIn,
    ClosureIn,
    DoctorIn,
    DoctorScheduleIn,
    DoctorUpdateIn,
    RoomIn,
    RoomUpdateIn,
    ScheduleIn,
    SettingVersionIn,
    SiteCreateIn,
    SiteUpdateIn,
)
from app.modules.users.models import AppUser, Role, user_role, user_site

_SETTING_FIELDS = (
    "valid_from",
    "daily_capacity",
    "slot_minutes",
    "tolerance_minutes",
    "max_concurrent_in_service",
    "registration_cutoff_minutes",
    "upcoming_notice_ahead",
    "allow_reregister_after_no_show",
    "allow_reregister_after_cancel",
    "notifications_enabled",
)
_SITE_FIELDS = ("name", "short_name", "address", "location_note", "is_active")
_ROOM_FIELDS = ("name", "location_note", "sort_order", "is_active")
_DOCTOR_FIELDS = ("full_name", "document_number", "cmp", "specialty", "phone", "email", "is_active")


class SiteConfigService:
    def __init__(self, ctx: ServiceContext) -> None:
        self.ctx = ctx
        self.db = ctx.db

    def update_site(self, site_id: int, data: SiteUpdateIn) -> Site:
        # Quien administra sedes puede editar (y reactivar) cualquiera, incluso una inactiva.
        if not self.ctx.user.has("site:manage"):
            self.ctx.require_site(site_id, action="SITE_UPDATE")
        site = sites.get_site(self.db, site_id)
        before = snapshot(site, _SITE_FIELDS)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(site, field, value)
        site.updated_by = self.ctx.user.id
        b, a = diff(before, snapshot(site, _SITE_FIELDS))
        self.ctx.audit(
            action="SITE_UPDATE", resource_type="site", resource_id=site.id, site_id=site.id, before=b, after=a
        )
        self.db.commit()
        return site

    def save_setting_version(self, site_id: int, data: SettingVersionIn) -> SiteSettingVersion:
        """Crea (o reemplaza, si aún no está vigente) la versión de configuración con vigencia futura."""
        self.ctx.require_site(site_id, action="SITE_SETTINGS_CHANGE")
        sites.get_site(self.db, site_id)
        sites.ensure_future_date(self.ctx.clock, data.valid_from)

        previous = sites.effective_setting(self.db, site_id, data.valid_from)
        version = self.db.scalar(
            select(SiteSettingVersion).where(
                SiteSettingVersion.site_id == site_id, SiteSettingVersion.valid_from == data.valid_from
            )
        )
        before = snapshot(previous, _SETTING_FIELDS) if previous else None
        values = data.model_dump()
        if version is None:
            version = SiteSettingVersion(site_id=site_id, created_by=self.ctx.user.id, **values)
            self.db.add(version)
        else:
            for field, value in values.items():
                setattr(version, field, value)
            version.updated_by = self.ctx.user.id
        self.db.flush()
        self.ctx.audit(
            action="SITE_SETTINGS_CHANGE",
            resource_type="site_setting_version",
            resource_id=version.id,
            site_id=site_id,
            reason=data.change_reason,
            before=before,
            after=snapshot(version, _SETTING_FIELDS),
        )
        self.db.commit()
        return version

    def replace_schedule(self, site_id: int, data: ScheduleIn) -> list[SiteSchedule]:
        """Nuevo horario semanal desde valid_from; el vigente se cierra el día anterior."""
        self.ctx.require_site(site_id, action="SITE_SCHEDULE_CHANGE")
        sites.get_site(self.db, site_id)
        sites.ensure_future_date(self.ctx.clock, data.valid_from)
        sites.assert_no_future_schedule_after(self.db, site_id, data.valid_from)

        keys = [(b.weekday, b.block) for b in data.blocks]
        if len(keys) != len(set(keys)):
            raise BusinessRuleError("SCHEDULE_OVERLAP", "Hay bloques repetidos para el mismo día.")

        current = sites.schedule_rows(self.db, site_id, data.valid_from)
        before = [snapshot(r, ("weekday", "block", "start_time", "end_time")) for r in current]
        for row in current:
            row.valid_to = data.valid_from - timedelta(days=1)
            row.updated_by = self.ctx.user.id
        self.db.flush()

        new_rows = [
            SiteSchedule(site_id=site_id, valid_from=data.valid_from, created_by=self.ctx.user.id, **b.model_dump())
            for b in data.blocks
        ]
        self.db.add_all(new_rows)
        self.db.flush()
        self.ctx.audit(
            action="SITE_SCHEDULE_CHANGE",
            resource_type="site",
            resource_id=site_id,
            site_id=site_id,
            reason=data.change_reason,
            before={"blocks": before},
            after={"valid_from": data.valid_from, "blocks": [b.model_dump() for b in data.blocks]},
        )
        self.db.commit()
        return new_rows

    def add_closure(self, site_id: int, data: ClosureIn) -> SiteClosure:
        self.ctx.require_site(site_id, action="SITE_CLOSURE_ADD")
        sites.get_site(self.db, site_id)
        if data.closure_date < self.ctx.clock.today():
            raise BusinessRuleError("DATE_NOT_ALLOWED", "No se pueden registrar cierres en fechas pasadas.")
        closure = SiteClosure(
            site_id=site_id, closure_date=data.closure_date, reason=data.reason, created_by=self.ctx.user.id
        )
        self.db.add(closure)
        self.db.flush()
        self.ctx.audit(
            action="SITE_CLOSURE_ADD",
            resource_type="site_closure",
            resource_id=closure.id,
            site_id=site_id,
            after=snapshot(closure, ("closure_date", "reason")),
        )
        self.db.commit()
        return closure

    def remove_closure(self, site_id: int, closure_id: int) -> None:
        self.ctx.require_site(site_id, action="SITE_CLOSURE_REMOVE")
        closure = self.db.get(SiteClosure, closure_id)
        if closure is None or closure.site_id != site_id:
            raise NotFoundError()
        if closure.closure_date < self.ctx.clock.today():
            raise BusinessRuleError("DATE_NOT_ALLOWED", "No se pueden eliminar cierres de fechas pasadas.")
        before = snapshot(closure, ("closure_date", "reason"))
        self.db.delete(closure)
        self.ctx.audit(
            action="SITE_CLOSURE_REMOVE",
            resource_type="site_closure",
            resource_id=closure_id,
            site_id=site_id,
            before=before,
        )
        self.db.commit()

    def adjust_capacity(self, site_id: int, day: date, data: CapacityAdjustIn) -> ServiceDay:
        """Ajuste explícito y auditado de la capacidad de un día ya abierto o por abrir (RN-08)."""
        self.ctx.require_site(site_id, action="SERVICE_DAY_CAPACITY_ADJUST")
        sites.get_site(self.db, site_id)
        if day < self.ctx.clock.today():
            raise BusinessRuleError("DATE_NOT_ALLOWED", "No se puede ajustar la capacidad de días pasados.")
        day_id = self.db.scalar(text("SELECT topico.ensure_service_day(:s, :d)"), {"s": site_id, "d": day})
        service_day = self.db.scalar(select(ServiceDay).where(ServiceDay.id == day_id).with_for_update(key_share=True))
        assert service_day is not None
        if data.capacity < service_day.occupied_count:
            raise BusinessRuleError(
                "CAPACITY_BELOW_OCCUPIED",
                f"La capacidad no puede ser menor que los {service_day.occupied_count} cupos ya ocupados.",
            )
        before = {"capacity": service_day.capacity}
        service_day.capacity = data.capacity
        service_day.capacity_adjusted_at = self.ctx.clock.now()
        service_day.capacity_adjusted_by = self.ctx.user.id
        service_day.capacity_adjust_reason = data.reason
        self.ctx.audit(
            action="SERVICE_DAY_CAPACITY_ADJUST",
            resource_type="service_day",
            resource_id=service_day.id,
            site_id=site_id,
            reason=data.reason,
            before=before,
            after={"capacity": data.capacity, "service_date": day},
        )
        self.db.commit()
        return service_day

    # ================================================================ médicos
    def create_doctor(self, site_id: int, data: DoctorIn) -> Doctor:
        self.ctx.require_site(site_id, action="DOCTOR_CREATE")
        sites.get_site(self.db, site_id)
        doctor = Doctor(site_id=site_id, **data.model_dump(), created_by=self.ctx.user.id, updated_by=self.ctx.user.id)
        self.db.add(doctor)
        self.db.flush()
        self.ctx.audit(
            action="DOCTOR_CREATE",
            resource_type="doctor",
            resource_id=doctor.id,
            site_id=site_id,
            after=snapshot(doctor, _DOCTOR_FIELDS),
        )
        self.db.commit()
        return doctor

    def update_doctor(self, site_id: int, doctor_id: int, data: DoctorUpdateIn) -> Doctor:
        self.ctx.require_site(site_id, action="DOCTOR_UPDATE")
        doctor = self.db.get(Doctor, doctor_id)
        if doctor is None or doctor.site_id != site_id:
            raise NotFoundError("DOCTOR_NOT_FOUND")
        before = snapshot(doctor, _DOCTOR_FIELDS)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(doctor, field, value)
        doctor.updated_by = self.ctx.user.id
        self.db.flush()
        if "is_active" in data.model_fields_set:
            sites.refresh_planned_capacity(self.db, site_id, self.ctx.clock, self.ctx.user.id)
        b, a = diff(before, snapshot(doctor, _DOCTOR_FIELDS))
        self.ctx.audit(
            action="DOCTOR_UPDATE", resource_type="doctor", resource_id=doctor.id, site_id=site_id, before=b, after=a
        )
        self.db.commit()
        return doctor

    # ================================================================ sedes nuevas
    def create_site(self, data: SiteCreateIn) -> Site:
        """Alta de sede con configuración y horario iniciales. Los administradores obtienen acceso a ella."""
        today = self.ctx.clock.today()
        valid_from = data.valid_from or today
        if valid_from < today:
            raise BusinessRuleError("DATE_NOT_ALLOWED", "La fecha de inicio no puede ser pasada.")
        keys = [(b.weekday, b.block) for b in data.blocks]
        if len(keys) != len(set(keys)):
            raise BusinessRuleError("SCHEDULE_OVERLAP", "Hay bloques repetidos para el mismo día.")

        user_id = self.ctx.user.id
        site = Site(
            code=data.code,
            name=data.name,
            short_name=data.short_name,
            ticket_prefix=data.ticket_prefix,
            address=data.address,
            location_note=data.location_note,
            is_active=True,
            created_by=user_id,
            updated_by=user_id,
        )
        self.db.add(site)
        self.db.flush()
        self.db.add(
            SiteSettingVersion(
                site_id=site.id,
                valid_from=valid_from,
                daily_capacity=data.daily_capacity,
                slot_minutes=data.slot_minutes,
                tolerance_minutes=data.tolerance_minutes,
                change_reason="Configuración inicial de la sede",
                created_by=user_id,
                updated_by=user_id,
            )
        )
        self.db.add_all(
            SiteSchedule(site_id=site.id, valid_from=valid_from, created_by=user_id, **b.model_dump())
            for b in data.blocks
        )
        admins = set(
            self.db.scalars(
                select(AppUser.id)
                .join(user_role, user_role.c.user_id == AppUser.id)
                .join(Role, Role.id == user_role.c.role_id)
                .where(Role.code == "ADMIN", AppUser.is_active)
            )
        )
        self.db.execute(
            insert(user_site),
            [{"user_id": uid, "site_id": site.id, "created_by": user_id} for uid in sorted(admins | {user_id})],
        )
        self.db.flush()
        self.ctx.audit(
            action="SITE_CREATE",
            resource_type="site",
            resource_id=site.id,
            site_id=site.id,
            after={
                **snapshot(site, ("code", "name", "short_name", "ticket_prefix", "address", "location_note")),
                "valid_from": valid_from,
                "daily_capacity": data.daily_capacity,
                "blocks": [b.model_dump() for b in data.blocks],
            },
        )
        self.db.commit()
        return site

    # ================================================================ consultorios
    def create_room(self, site_id: int, data: RoomIn) -> ConsultingRoom:
        self.ctx.require_site(site_id, action="ROOM_CREATE")
        sites.get_site(self.db, site_id)
        room = ConsultingRoom(
            site_id=site_id, **data.model_dump(), created_by=self.ctx.user.id, updated_by=self.ctx.user.id
        )
        self.db.add(room)
        self.db.flush()
        self.ctx.audit(
            action="ROOM_CREATE",
            resource_type="consulting_room",
            resource_id=room.id,
            site_id=site_id,
            after=snapshot(room, _ROOM_FIELDS),
        )
        self.db.commit()
        return room

    def update_room(self, site_id: int, room_id: int, data: RoomUpdateIn) -> ConsultingRoom:
        self.ctx.require_site(site_id, action="ROOM_UPDATE")
        room = self.db.get(ConsultingRoom, room_id)
        if room is None or room.site_id != site_id:
            raise NotFoundError("ROOM_NOT_FOUND")
        before = snapshot(room, _ROOM_FIELDS)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(room, field, value)
        room.updated_by = self.ctx.user.id
        self.db.flush()
        b, a = diff(before, snapshot(room, _ROOM_FIELDS))
        self.ctx.audit(
            action="ROOM_UPDATE",
            resource_type="consulting_room",
            resource_id=room.id,
            site_id=site_id,
            before=b,
            after=a,
        )
        self.db.commit()
        return room

    # ================================================================ horario y ausencias de médicos
    def _doctor(self, site_id: int, doctor_id: int, action: str) -> Doctor:
        self.ctx.require_site(site_id, action=action)
        doctor = self.db.get(Doctor, doctor_id)
        if doctor is None or doctor.site_id != site_id:
            raise NotFoundError("DOCTOR_NOT_FOUND")
        return doctor

    def replace_doctor_schedule(self, site_id: int, doctor_id: int, data: DoctorScheduleIn) -> None:
        doctor = self._doctor(site_id, doctor_id, "DOCTOR_SCHEDULE_CHANGE")
        by_day: dict[int, list[tuple[object, object]]] = {}
        for b in sorted(data.blocks, key=lambda b: (b.weekday, b.start_time)):
            previous = by_day.setdefault(b.weekday, [])
            if previous and b.start_time < previous[-1][1]:  # type: ignore[operator]
                raise BusinessRuleError("SCHEDULE_OVERLAP_DOCTOR")
            previous.append((b.start_time, b.end_time))
        current = list(self.db.scalars(select(DoctorSchedule).where(DoctorSchedule.doctor_id == doctor.id)))
        before = [snapshot(r, ("weekday", "start_time", "end_time")) for r in current]
        for row in current:
            self.db.delete(row)
        self.db.flush()
        self.db.add_all(
            DoctorSchedule(doctor_id=doctor.id, created_by=self.ctx.user.id, **b.model_dump()) for b in data.blocks
        )
        self.db.flush()
        sites.refresh_planned_capacity(self.db, site_id, self.ctx.clock, self.ctx.user.id)
        self.ctx.audit(
            action="DOCTOR_SCHEDULE_CHANGE",
            resource_type="doctor",
            resource_id=doctor.id,
            site_id=site_id,
            before={"blocks": before},
            after={"blocks": [b.model_dump(mode="json") for b in data.blocks]},
        )
        self.db.commit()

    def add_absence(self, site_id: int, doctor_id: int, data: AbsenceIn) -> DoctorAbsence:
        doctor = self._doctor(site_id, doctor_id, "DOCTOR_ABSENCE_ADD")
        if data.date_to < self.ctx.clock.today():
            raise BusinessRuleError("DATE_NOT_ALLOWED", "No se registran ausencias en fechas pasadas.")
        absence = DoctorAbsence(doctor_id=doctor.id, created_by=self.ctx.user.id, **data.model_dump())
        self.db.add(absence)
        self.db.flush()
        sites.refresh_planned_capacity(self.db, site_id, self.ctx.clock, self.ctx.user.id)
        self.ctx.audit(
            action="DOCTOR_ABSENCE_ADD",
            resource_type="doctor",
            resource_id=doctor.id,
            site_id=site_id,
            after=snapshot(absence, ("date_from", "date_to", "reason")),
        )
        self.db.commit()
        return absence

    def remove_absence(self, site_id: int, doctor_id: int, absence_id: int) -> None:
        doctor = self._doctor(site_id, doctor_id, "DOCTOR_ABSENCE_REMOVE")
        absence = self.db.get(DoctorAbsence, absence_id)
        if absence is None or absence.doctor_id != doctor.id:
            raise NotFoundError("DOCTOR_ABSENCE_NOT_FOUND")
        before = snapshot(absence, ("date_from", "date_to", "reason"))
        self.db.delete(absence)
        self.db.flush()
        sites.refresh_planned_capacity(self.db, site_id, self.ctx.clock, self.ctx.user.id)
        self.ctx.audit(
            action="DOCTOR_ABSENCE_REMOVE",
            resource_type="doctor",
            resource_id=doctor.id,
            site_id=site_id,
            before=before,
        )
        self.db.commit()
