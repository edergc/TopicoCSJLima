"""Importación de trabajadores EPS Rímac: staging → validación → previsualización → confirmación."""

import hashlib
import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select, true
from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.core.logging import get_logger
from app.modules.audit import service as audit
from app.modules.auth.dependencies import ServiceContext
from app.modules.imports.models import ImportBatch, ImportRow
from app.modules.imports.parsing import WORKER_FIELDS, ParsedRow, read_workbook
from app.modules.workers import service as workers
from app.modules.workers.models import Department, Worker, WorkerCoverage

log = get_logger(__name__)

KIND_WORKERS = "WORKERS_EPS"
_COUNT_FIELDS = ("new_count", "update_count", "unchanged_count", "error_count", "duplicate_count")


def _current_values(worker: Worker) -> dict[str, Any]:
    return {
        "first_names": worker.first_names,
        "paternal_surname": worker.paternal_surname,
        "maternal_surname": worker.maternal_surname,
        "sex": worker.sex,
        "birth_date": worker.birth_date.isoformat() if worker.birth_date else None,
        "institutional_email": worker.institutional_email,
        "phone": worker.phone,
        "department_name": worker.department.name if worker.department else None,
        "employee_code": worker.employee_code,
    }


def _changes(worker: Worker, normalized: dict[str, Any], today: date) -> dict[str, list[Any]]:
    current = _current_values(worker)
    changes: dict[str, list[Any]] = {}
    for field in WORKER_FIELDS:
        new = normalized.get(field)
        # Un dato vacío en el Excel no borra un dato existente.
        if new is not None and new != current[field]:
            changes[field] = [current[field], new]
    if not worker.is_active:
        changes["is_active"] = [False, True]
    if worker.coverage_on(today, workers.ELIGIBLE_INSURER) is None:
        changes["coverage"] = ["SIN COBERTURA", "VIGENTE"]
    return changes


class ImportService:
    def __init__(self, ctx: ServiceContext) -> None:
        self.ctx = ctx
        self.db: Session = ctx.db

    # ----------------------------------------------------------------- upload
    def upload(self, file_name: str, content: bytes, kind: str) -> ImportBatch:
        if kind != KIND_WORKERS:
            raise BusinessRuleError(
                "IMPORT_FILE_INVALID",
                "La importación del histórico de atenciones se habilitará cuando se defina el formato del Excel.",
            )
        if not file_name.lower().endswith(".xlsx"):
            raise BusinessRuleError("IMPORT_FILE_INVALID", "Solo se aceptan archivos Excel .xlsx.")
        max_bytes = self.ctx.settings.max_upload_mb * 1024 * 1024
        if not content or len(content) > max_bytes:
            raise BusinessRuleError("PAYLOAD_TOO_LARGE" if content else "IMPORT_EMPTY")

        sha = hashlib.sha256(content).hexdigest()
        if self.db.scalar(
            select(ImportBatch.id).where(
                ImportBatch.kind == kind, ImportBatch.file_sha256 == sha, ImportBatch.status == "CONFIRMED"
            )
        ):
            raise ConflictError("IMPORT_ALREADY_CONFIRMED")

        sheet = read_workbook(content)
        batch = ImportBatch(
            kind=kind,
            status="UPLOADED",
            file_name=file_name[-255:],
            file_sha256=sha,
            file_size_bytes=len(content),
            sheet_name=sheet.sheet_name[:100],
            column_mapping={"mapped": sheet.mapping, "ignored": sheet.ignored_columns},
            options={},
            created_by=self.ctx.user.id,
        )
        self.db.add(batch)
        self.db.flush()
        self._validate(batch, sheet.rows)
        self.ctx.audit(
            action="IMPORT_UPLOAD",
            resource_type="import_batch",
            resource_id=batch.public_id,
            metadata={
                "file": file_name,
                "sha256": sha,
                "rows": batch.total_rows,
                **{f: getattr(batch, f) for f in _COUNT_FIELDS},
            },
        )
        self.db.commit()
        return batch

    def _validate(self, batch: ImportBatch, rows: list[ParsedRow]) -> None:
        today = self.ctx.clock.today()
        dnis = {r.normalized.get("document_number") for r in rows if not r.errors}
        existing = {
            w.document_number: w
            for w in self.db.scalars(
                select(Worker).where(Worker.document_type == "DNI", Worker.document_number.in_(dnis))
            ).unique()
        }
        seen: dict[str, int] = {}
        records: list[ImportRow] = []
        for row in rows:
            dni = str(row.normalized.get("document_number") or "")
            outcome, changes, target = "ERROR", None, None
            if not row.errors:
                if dni in seen:
                    outcome = "DUPLICATE_IN_FILE"
                    row.warnings.append(f"DNI repetido en el archivo (ya aparece en la fila {seen[dni]}).")
                else:
                    seen[dni] = row.row_number
                    worker = existing.get(dni)
                    if worker is None:
                        outcome = "NEW"
                    else:
                        target = worker.id
                        changes = _changes(worker, row.normalized, today)
                        outcome = "UPDATE" if changes else "UNCHANGED"
            records.append(
                ImportRow(
                    batch_id=batch.id,
                    row_number=row.row_number,
                    raw=row.raw,
                    normalized=row.normalized,
                    outcome=outcome,
                    errors=row.errors,
                    warnings=row.warnings,
                    changes=changes,
                    target_worker_id=target,
                )
            )
        self.db.add_all(records)
        counts = {
            o: sum(1 for r in records if r.outcome == o)
            for o in ("NEW", "UPDATE", "UNCHANGED", "ERROR", "DUPLICATE_IN_FILE")
        }
        batch.total_rows = len(records)
        batch.new_count = counts["NEW"]
        batch.update_count = counts["UPDATE"]
        batch.unchanged_count = counts["UNCHANGED"]
        batch.error_count = counts["ERROR"]
        batch.duplicate_count = counts["DUPLICATE_IN_FILE"]
        batch.status = "VALIDATED"
        batch.validated_at = self.ctx.clock.now()

    # --------------------------------------------------------------- confirm
    def confirm(self, public_id: uuid.UUID, *, deactivate_missing: bool) -> ImportBatch:
        batch = self._get(public_id, for_update=True)
        if batch.status != "VALIDATED":
            raise ConflictError("IMPORT_INVALID_STATE")
        try:
            deactivated = self._apply(batch, deactivate_missing)
        except Exception as exc:
            self.db.rollback()
            self._mark_failed(public_id, exc)
            raise
        now = self.ctx.clock.now()
        batch.status = "CONFIRMED"
        batch.confirmed_at, batch.confirmed_by = now, self.ctx.user.id
        batch.deactivated_count = deactivated
        batch.options = {"deactivate_missing": deactivate_missing}
        self.ctx.audit(
            action="IMPORT_CONFIRM",
            resource_type="import_batch",
            resource_id=batch.public_id,
            metadata={
                "file": batch.file_name,
                "new": batch.new_count,
                "updated": batch.update_count,
                "unchanged": batch.unchanged_count,
                "errors": batch.error_count,
                "coverage_ended": deactivated,
                "deactivate_missing": deactivate_missing,
            },
        )
        self.db.commit()
        return batch

    def _apply(self, batch: ImportBatch, deactivate_missing: bool) -> int:
        today = self.ctx.clock.today()
        user_id = self.ctx.user.id
        insurer = workers.rimac(self.db)
        departments: dict[str, Department] = {}

        def department_id(name: str | None) -> int | None:
            if not name:
                return None
            if name not in departments:
                departments[name] = workers.get_or_create_department(self.db, name)
            return departments[name].id

        rows = self.db.scalars(
            select(ImportRow)
            .where(ImportRow.batch_id == batch.id, ImportRow.outcome.in_(("NEW", "UPDATE", "UNCHANGED")))
            .order_by(ImportRow.row_number)
        ).all()
        listed_worker_ids: set[int] = set()

        for row in rows:
            n = row.normalized or {}
            birth = date.fromisoformat(n["birth_date"]) if n.get("birth_date") else None
            if row.outcome == "NEW":
                worker = Worker(
                    document_type="DNI",
                    document_number=n["document_number"],
                    first_names=n["first_names"],
                    paternal_surname=n["paternal_surname"],
                    maternal_surname=n.get("maternal_surname"),
                    sex=n.get("sex"),
                    birth_date=birth,
                    institutional_email=n.get("institutional_email"),
                    phone=n.get("phone"),
                    employee_code=n.get("employee_code"),
                    department_id=department_id(n.get("department_name")),
                    is_active=True,
                    source_import_id=batch.id,
                    created_by=user_id,
                    updated_by=user_id,
                )
                self.db.add(worker)
                self.db.flush()
                self.db.add(
                    WorkerCoverage(
                        worker_id=worker.id,
                        insurer_id=insurer.id,
                        valid_from=today,
                        source_import_id=batch.id,
                        created_by=user_id,
                    )
                )
                listed_worker_ids.add(worker.id)
                continue

            existing = self.db.get(Worker, row.target_worker_id)
            assert existing is not None
            worker = existing
            listed_worker_ids.add(worker.id)
            if row.outcome == "UNCHANGED":
                continue
            changes = row.changes or {}
            for field, (_, new) in changes.items():
                if field == "department_name":
                    worker.department_id = department_id(new)
                elif field == "birth_date":
                    worker.birth_date = date.fromisoformat(new) if new else None
                elif field == "is_active":
                    worker.is_active, worker.deactivated_at, worker.deactivation_reason = True, None, None
                elif field != "coverage":
                    setattr(worker, field, new)
            if "coverage" in changes and worker.coverage_on(today, workers.ELIGIBLE_INSURER) is None:
                self.db.add(
                    WorkerCoverage(
                        worker_id=worker.id,
                        insurer_id=insurer.id,
                        valid_from=today,
                        source_import_id=batch.id,
                        created_by=user_id,
                    )
                )
            worker.source_import_id = batch.id
            worker.updated_by = user_id
        self.db.flush()

        if not deactivate_missing:
            return 0
        # Cobertura vigente de trabajadores que ya no figuran en la relación: se da por terminada.
        open_coverages = self.db.scalars(
            select(WorkerCoverage).where(
                WorkerCoverage.insurer_id == insurer.id,
                WorkerCoverage.valid_from <= today,
                (WorkerCoverage.valid_to.is_(None)) | (WorkerCoverage.valid_to >= today),
                WorkerCoverage.worker_id.not_in(listed_worker_ids) if listed_worker_ids else true(),
            )
        ).all()
        for coverage in open_coverages:
            coverage.valid_to = max(today - timedelta(days=1), coverage.valid_from)
            coverage.end_reason = f"No figura en la importación {batch.file_name}"[:200]
            coverage.updated_by = user_id
        return len(open_coverages)

    def _mark_failed(self, public_id: uuid.UUID, exc: Exception) -> None:
        log.exception("import_confirm_failed", batch=str(public_id))
        with self.ctx.session_factory() as db:
            batch = db.scalar(select(ImportBatch).where(ImportBatch.public_id == public_id))
            if batch is not None:
                batch.status = "FAILED"
                batch.failure_message = f"{type(exc).__name__}: {exc}"[:1000]
                audit.record(
                    db,
                    action="IMPORT_CONFIRM",
                    actor=self.ctx.user,
                    result="FAILURE",
                    resource_type="import_batch",
                    resource_id=public_id,
                    reason=batch.failure_message,
                )
                db.commit()

    # --------------------------------------------------------------- otros
    def discard(self, public_id: uuid.UUID) -> ImportBatch:
        batch = self._get(public_id, for_update=True)
        if batch.status not in ("UPLOADED", "VALIDATED"):
            raise ConflictError("IMPORT_INVALID_STATE")
        batch.status = "DISCARDED"
        batch.discarded_at, batch.discarded_by = self.ctx.clock.now(), self.ctx.user.id
        self.ctx.audit(action="IMPORT_DISCARD", resource_type="import_batch", resource_id=batch.public_id)
        self.db.commit()
        return batch

    def _get(self, public_id: uuid.UUID, *, for_update: bool = False) -> ImportBatch:
        stmt = select(ImportBatch).where(ImportBatch.public_id == public_id)
        if for_update:
            stmt = stmt.with_for_update(key_share=True)
        batch = self.db.scalar(stmt)
        if batch is None:
            raise NotFoundError()
        return batch

    def get(self, public_id: uuid.UUID) -> ImportBatch:
        return self._get(public_id)

    def rows(self, public_id: uuid.UUID, outcome: str | None, offset: int, limit: int) -> tuple[list[ImportRow], int]:
        batch = self._get(public_id)
        stmt = select(ImportRow).where(ImportRow.batch_id == batch.id)
        if outcome:
            stmt = stmt.where(ImportRow.outcome == outcome)
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = self.db.scalars(stmt.order_by(ImportRow.row_number).offset(offset).limit(limit)).all()
        return list(items), int(total)
