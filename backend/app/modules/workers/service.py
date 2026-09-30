"""Trabajadores: elegibilidad EPS, búsqueda y mantenimiento administrativo."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleError, NotFoundError
from app.modules.audit.service import diff, snapshot
from app.modules.auth.dependencies import ServiceContext
from app.modules.workers.models import Department, Insurer, Worker, WorkerCoverage
from app.modules.workers.schemas import CoverageEndIn, CoverageIn, WorkerCreateIn, WorkerUpdateIn
from app.shared.text import is_valid_dni, normalize_document, normalize_key

ELIGIBLE_INSURER = "RIMAC"

WORKER_AUDIT_FIELDS = (
    "document_type",
    "document_number",
    "first_names",
    "paternal_surname",
    "maternal_surname",
    "birth_date",
    "sex",
    "institutional_email",
    "phone",
    "employee_code",
    "department_id",
    "work_site_id",
    "is_active",
    "deactivation_reason",
)


@dataclass(frozen=True)
class Eligibility:
    worker: Worker | None
    eligible: bool
    code: str | None  # WORKER_NOT_FOUND | WORKER_INACTIVE | WORKER_NOT_ELIGIBLE
    coverage: WorkerCoverage | None


def parse_dni(raw: str) -> str:
    value = normalize_document(raw)
    if not is_valid_dni(value):
        raise BusinessRuleError("INVALID_DOCUMENT")
    return value


def find_by_document(db: Session, document_number: str, document_type: str = "DNI") -> Worker | None:
    return db.scalar(
        select(Worker).where(Worker.document_type == document_type, Worker.document_number == document_number)
    )


def check_eligibility(db: Session, document_number: str, on: date) -> Eligibility:
    """Regla RN-01: existe → activo → cobertura EPS Rímac vigente a la fecha."""
    worker = find_by_document(db, document_number)
    if worker is None:
        return Eligibility(None, False, "WORKER_NOT_FOUND", None)
    if not worker.is_active:
        return Eligibility(worker, False, "WORKER_INACTIVE", None)
    coverage = worker.coverage_on(on, ELIGIBLE_INSURER)
    if coverage is None:
        return Eligibility(worker, False, "WORKER_NOT_ELIGIBLE", None)
    return Eligibility(worker, True, None, coverage)


def get_worker(db: Session, public_id: object) -> Worker:
    worker = db.scalar(select(Worker).where(Worker.public_id == public_id))
    if worker is None:
        raise NotFoundError("WORKER_NOT_FOUND", "El trabajador no existe.")
    return worker


def search(db: Session, q: str | None, *, active: bool | None, offset: int, limit: int) -> tuple[list[Worker], int]:
    stmt = select(Worker)
    if q:
        term = q.strip()
        digits = normalize_document(term)
        if digits.isdigit():
            stmt = stmt.where(Worker.document_number.startswith(digits))
        else:
            pattern = f"%{normalize_key(term)}%"
            stmt = stmt.where(or_(Worker.search_name.ilike(pattern), Worker.institutional_email.ilike(f"%{term}%")))
    if active is not None:
        stmt = stmt.where(Worker.is_active.is_(active))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Worker.search_name).offset(offset).limit(limit)).all()
    return list(rows), int(total)


def get_or_create_department(db: Session, name: str) -> Department:
    key = normalize_key(name)
    department = db.scalar(select(Department).where(Department.normalized_name == key))
    if department is None:
        department = Department(name=" ".join(name.split()).upper(), normalized_name=key)
        db.add(department)
        db.flush()
    return department


def rimac(db: Session) -> Insurer:
    insurer = db.scalar(select(Insurer).where(Insurer.code == ELIGIBLE_INSURER))
    if insurer is None:  # pragma: no cover - dato de referencia
        raise RuntimeError("Falta la EPS RIMAC en los datos de referencia")
    return insurer


class WorkerService:
    def __init__(self, ctx: ServiceContext) -> None:
        self.ctx = ctx
        self.db = ctx.db

    def view(self, public_id: object) -> Worker:
        """Ficha completa de un trabajador: la lectura de datos personales queda auditada."""
        worker = get_worker(self.db, public_id)
        self.ctx.audit(action="WORKER_VIEW", resource_type="worker", resource_id=worker.public_id)
        self.db.commit()
        return worker

    def create(self, data: WorkerCreateIn) -> Worker:
        values = data.model_dump(exclude={"department_name", "coverage_valid_from"})
        values["document_number"] = parse_dni(data.document_number)
        if data.department_name:
            values["department_id"] = get_or_create_department(self.db, data.department_name).id
        worker = Worker(**values, created_by=self.ctx.user.id, updated_by=self.ctx.user.id)
        self.db.add(worker)
        self.db.flush()
        if data.coverage_valid_from:
            self.db.add(
                WorkerCoverage(
                    worker_id=worker.id,
                    insurer_id=rimac(self.db).id,
                    valid_from=data.coverage_valid_from,
                    created_by=self.ctx.user.id,
                )
            )
        self.ctx.audit(
            action="WORKER_CREATE",
            resource_type="worker",
            resource_id=worker.public_id,
            after=snapshot(worker, WORKER_AUDIT_FIELDS),
        )
        self.db.commit()
        self.db.refresh(worker)
        return worker

    def update(self, public_id: object, data: WorkerUpdateIn) -> Worker:
        worker = get_worker(self.db, public_id)
        before = snapshot(worker, WORKER_AUDIT_FIELDS)
        values = data.model_dump(exclude_unset=True, exclude={"department_name"})
        if data.department_name is not None:
            values["department_id"] = get_or_create_department(self.db, data.department_name).id
        if values.get("is_active") is False and worker.is_active:
            if not data.deactivation_reason:
                raise BusinessRuleError("VALIDATION_ERROR", "Indique el motivo de la desactivación.")
            worker.deactivated_at = self.ctx.clock.now()
        if values.get("is_active") is True:
            worker.deactivated_at = None
            values["deactivation_reason"] = None
        for field, value in values.items():
            setattr(worker, field, value)
        worker.updated_by = self.ctx.user.id
        self.db.flush()
        b, a = diff(before, snapshot(worker, WORKER_AUDIT_FIELDS))
        if a:
            self.ctx.audit(
                action="WORKER_UPDATE", resource_type="worker", resource_id=worker.public_id, before=b, after=a
            )
        self.db.commit()
        self.db.refresh(worker)
        return worker

    def add_coverage(self, public_id: object, data: CoverageIn) -> Worker:
        worker = get_worker(self.db, public_id)
        coverage = WorkerCoverage(
            worker_id=worker.id,
            insurer_id=rimac(self.db).id,
            valid_from=data.valid_from,
            valid_to=data.valid_to,
            created_by=self.ctx.user.id,
        )
        self.db.add(coverage)
        self.db.flush()
        self.ctx.audit(
            action="WORKER_COVERAGE_ADD",
            resource_type="worker",
            resource_id=worker.public_id,
            after=snapshot(coverage, ("valid_from", "valid_to")),
        )
        self.db.commit()
        self.db.refresh(worker)
        return worker

    def end_coverage(self, public_id: object, coverage_id: int, data: CoverageEndIn) -> Worker:
        worker = get_worker(self.db, public_id)
        coverage = next((c for c in worker.coverages if c.id == coverage_id), None)
        if coverage is None:
            raise NotFoundError()
        if data.valid_to < coverage.valid_from:
            raise BusinessRuleError("VALIDATION_ERROR", "La fecha de término no puede ser anterior al inicio.")
        before = snapshot(coverage, ("valid_to", "end_reason"))
        coverage.valid_to = data.valid_to
        coverage.end_reason = data.end_reason
        coverage.updated_by = self.ctx.user.id
        self.ctx.audit(
            action="WORKER_COVERAGE_END",
            resource_type="worker",
            resource_id=worker.public_id,
            before=before,
            after=snapshot(coverage, ("valid_to", "end_reason")),
        )
        self.db.commit()
        self.db.refresh(worker)
        return worker
