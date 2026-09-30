import csv
import io
import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from app.modules.auth.dependencies import ServiceContext, require
from app.modules.imports.models import ImportBatch, ImportRow
from app.modules.imports.service import ImportService
from app.shared.schemas import ApiModel, ApiOut, Page, PageParams

router = APIRouter(prefix="/imports", tags=["Importación de Excel"])

Ctx = Annotated[ServiceContext, Depends(require("import:manage"))]


class ImportBatchOut(ApiOut):
    public_id: uuid.UUID
    kind: str
    status: str
    file_name: str
    file_sha256: str
    file_size_bytes: int
    sheet_name: str | None
    column_mapping: dict[str, Any] | None
    options: dict[str, Any]
    total_rows: int
    new_count: int
    update_count: int
    unchanged_count: int
    error_count: int
    duplicate_count: int
    deactivated_count: int
    failure_message: str | None
    created_at: datetime
    validated_at: datetime | None
    confirmed_at: datetime | None
    discarded_at: datetime | None


class ImportRowOut(ApiOut):
    row_number: int
    outcome: str
    raw: dict[str, Any]
    normalized: dict[str, Any] | None
    errors: list[str]
    warnings: list[str]
    changes: dict[str, Any] | None


class ConfirmIn(ApiModel):
    deactivate_missing: bool = False


@router.post("", response_model=ImportBatchOut, status_code=201, summary="Cargar y validar un Excel (sin aplicar)")
async def upload(
    ctx: Ctx,
    file: Annotated[UploadFile, File(description="Archivo .xlsx")],
    kind: Annotated[Literal["WORKERS_EPS", "HISTORICAL_APPOINTMENTS"], Form()] = "WORKERS_EPS",
) -> ImportBatch:
    limit = ctx.settings.max_upload_mb * 1024 * 1024
    content = await file.read(limit + 1)
    return ImportService(ctx).upload(file.filename or "archivo.xlsx", content, kind)


@router.get("", response_model=Page[ImportBatchOut], summary="Historial de importaciones")
def list_batches(ctx: Ctx, paging: Annotated[PageParams, Depends()]) -> Page[ImportBatchOut]:
    total = ctx.db.scalar(select(func.count()).select_from(ImportBatch)) or 0
    rows = ctx.db.scalars(select(ImportBatch).order_by(ImportBatch.id.desc()).offset(paging.offset).limit(paging.size))
    return Page(items=[ImportBatchOut.model_validate(b) for b in rows], total=total, page=paging.page, size=paging.size)


@router.get("/{public_id}", response_model=ImportBatchOut)
def get_batch(public_id: uuid.UUID, ctx: Ctx) -> ImportBatch:
    return ImportService(ctx).get(public_id)


@router.get("/{public_id}/rows", response_model=Page[ImportRowOut], summary="Previsualización fila por fila")
def get_rows(
    public_id: uuid.UUID,
    ctx: Ctx,
    paging: Annotated[PageParams, Depends()],
    outcome: Annotated[str | None, Query(max_length=20)] = None,
) -> Page[ImportRowOut]:
    rows, total = ImportService(ctx).rows(public_id, outcome, paging.offset, paging.size)
    return Page(items=[ImportRowOut.model_validate(r) for r in rows], total=total, page=paging.page, size=paging.size)


@router.get("/{public_id}/errors.csv", summary="Descargar reporte de errores y advertencias")
def download_errors(public_id: uuid.UUID, ctx: Ctx) -> StreamingResponse:
    batch = ImportService(ctx).get(public_id)
    rows = ctx.db.scalars(
        select(ImportRow)
        .where(
            ImportRow.batch_id == batch.id,
            (ImportRow.outcome.in_(("ERROR", "DUPLICATE_IN_FILE"))) | (func.jsonb_array_length(ImportRow.warnings) > 0),
        )
        .order_by(ImportRow.row_number)
    )
    buffer = io.StringIO()
    buffer.write("﻿")  # BOM: Excel reconoce UTF-8
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(["Fila", "Resultado", "DNI", "Errores", "Advertencias"])
    for r in rows:
        writer.writerow(
            [
                r.row_number,
                r.outcome,
                (r.normalized or {}).get("document_number", ""),
                " | ".join(r.errors),
                " | ".join(r.warnings),
            ]
        )
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="errores_importacion_{batch.public_id}.csv"'},
    )


@router.post("/{public_id}/confirm", response_model=ImportBatchOut, summary="Confirmar e incorporar (transaccional)")
def confirm(public_id: uuid.UUID, body: ConfirmIn, ctx: Ctx) -> ImportBatch:
    return ImportService(ctx).confirm(public_id, deactivate_missing=body.deactivate_missing)


@router.post("/{public_id}/discard", response_model=ImportBatchOut, summary="Descartar el lote")
def discard(public_id: uuid.UUID, ctx: Ctx) -> ImportBatch:
    return ImportService(ctx).discard(public_id)
