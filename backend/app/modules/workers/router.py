import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.core.errors import MESSAGES
from app.modules.appointments.models import Appointment
from app.modules.auth.dependencies import ServiceContext, require
from app.modules.workers import service as workers
from app.modules.workers.models import Department, Worker, WorkerCoverage
from app.modules.workers.schemas import (
    CoverageEndIn,
    CoverageIn,
    CoverageOut,
    DepartmentOut,
    EligibilityOut,
    TodayAppointmentOut,
    WorkerCreateIn,
    WorkerOut,
    WorkerSummaryOut,
    WorkerUpdateIn,
)
from app.shared.schemas import Page, PageParams

router = APIRouter(prefix="/workers", tags=["Trabajadores"])
catalog_router = APIRouter(prefix="/catalogs", tags=["Catálogos"])

ACTIVE_STATUSES = ("REGISTRADO", "EN_ESPERA", "LLAMADO", "EN_ATENCION")


def coverage_out(c: WorkerCoverage) -> CoverageOut:
    return CoverageOut(
        id=c.id,
        insurer_code=c.insurer.code,
        insurer_name=c.insurer.name,
        valid_from=c.valid_from,
        valid_to=c.valid_to,
        end_reason=c.end_reason,
    )


def _summary_fields(w: Worker) -> dict[str, object]:
    return {
        "public_id": w.public_id,
        "document_type": w.document_type,
        "document_number": w.document_number,
        "first_names": w.first_names,
        "paternal_surname": w.paternal_surname,
        "maternal_surname": w.maternal_surname,
        "department_name": w.department.name if w.department else None,
        "has_email": bool(w.institutional_email),
        "has_phone": bool(w.phone),
        "is_active": w.is_active,
    }


def summary_out(w: Worker) -> WorkerSummaryOut:
    return WorkerSummaryOut.model_validate(_summary_fields(w))


def worker_out(w: Worker, ctx: ServiceContext) -> WorkerOut:
    return WorkerOut.model_validate(
        {
            **_summary_fields(w),
            "birth_date": w.birth_date,
            "age": w.age_on(ctx.clock.today()),
            "sex": w.sex,
            "institutional_email": w.institutional_email,
            "phone": w.phone,
            "employee_code": w.employee_code,
            "department_id": w.department_id,
            "work_site_id": w.work_site_id,
            "deactivated_at": w.deactivated_at,
            "deactivation_reason": w.deactivation_reason,
            "coverages": [coverage_out(c) for c in w.coverages],
            "created_at": w.created_at,
            "updated_at": w.updated_at,
        }
    )


@router.get("/eligibility", response_model=EligibilityOut, summary="Búsqueda rápida por DNI y verificación EPS")
def eligibility(
    ctx: Annotated[ServiceContext, Depends(require("worker:lookup"))],
    document_number: Annotated[str, Query(min_length=5, max_length=12)],
) -> EligibilityOut:
    dni = workers.parse_dni(document_number)
    today = ctx.clock.today()
    result = workers.check_eligibility(ctx.db, dni, today)
    active = None
    if result.worker is not None:
        appt = ctx.db.scalar(
            select(Appointment)
            .where(
                Appointment.worker_id == result.worker.id,
                Appointment.service_date >= today,
                Appointment.status.in_(ACTIVE_STATUSES),
            )
            .order_by(Appointment.service_date)
            .limit(1)
        )
        if appt is not None:
            active = TodayAppointmentOut(
                public_id=appt.public_id,
                ticket_code=appt.ticket_code,
                status=appt.status,
                site_id=appt.site_id,
                site_name=appt.site.name,
                service_date=appt.service_date,
            )
    return EligibilityOut(
        document_number=dni,
        found=result.worker is not None,
        eligible=result.eligible,
        code=result.code,
        message=MESSAGES[result.code] if result.code else "Trabajador habilitado · EPS Rímac vigente.",
        worker=summary_out(result.worker) if result.worker else None,
        coverage=coverage_out(result.coverage) if result.coverage else None,
        active_appointment=active,
    )


@router.get("", response_model=Page[WorkerSummaryOut], summary="Buscar trabajadores (DNI o nombre)")
def search_workers(
    ctx: Annotated[ServiceContext, Depends(require("worker:read"))],
    paging: Annotated[PageParams, Depends()],
    q: Annotated[str | None, Query(max_length=100)] = None,
    active: bool | None = None,
) -> Page[WorkerSummaryOut]:
    rows, total = workers.search(ctx.db, q, active=active, offset=paging.offset, limit=paging.size)
    return Page(items=[summary_out(w) for w in rows], total=total, page=paging.page, size=paging.size)


@router.get("/{public_id}", response_model=WorkerOut, summary="Ficha del trabajador (lectura auditada)")
def get_worker(public_id: uuid.UUID, ctx: Annotated[ServiceContext, Depends(require("worker:read"))]) -> WorkerOut:
    return worker_out(workers.WorkerService(ctx).view(public_id), ctx)


ManageCtx = Annotated[ServiceContext, Depends(require("worker:manage"))]


@router.post("", response_model=WorkerOut, status_code=201, summary="Registrar trabajador")
def create_worker(body: WorkerCreateIn, ctx: ManageCtx) -> WorkerOut:
    return worker_out(workers.WorkerService(ctx).create(body), ctx)


@router.patch("/{public_id}", response_model=WorkerOut, summary="Modificar trabajador")
def update_worker(public_id: uuid.UUID, body: WorkerUpdateIn, ctx: ManageCtx) -> WorkerOut:
    return worker_out(workers.WorkerService(ctx).update(public_id, body), ctx)


@router.post("/{public_id}/coverages", response_model=WorkerOut, status_code=201, summary="Agregar cobertura EPS")
def add_coverage(public_id: uuid.UUID, body: CoverageIn, ctx: ManageCtx) -> WorkerOut:
    return worker_out(workers.WorkerService(ctx).add_coverage(public_id, body), ctx)


@router.post("/{public_id}/coverages/{coverage_id}/end", response_model=WorkerOut, summary="Terminar cobertura EPS")
def end_coverage(public_id: uuid.UUID, coverage_id: int, body: CoverageEndIn, ctx: ManageCtx) -> WorkerOut:
    return worker_out(workers.WorkerService(ctx).end_coverage(public_id, coverage_id, body), ctx)


@catalog_router.get("/departments", response_model=list[DepartmentOut], summary="Dependencias")
def list_departments(ctx: Annotated[ServiceContext, Depends(require())]) -> list[Department]:
    return list(ctx.db.scalars(select(Department).where(Department.is_active).order_by(Department.name)))
