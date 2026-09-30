import csv
import io
from datetime import date, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook

from app.core.clock import INSTITUTION_TZ
from app.modules.auth.dependencies import ServiceContext, require
from app.modules.reports import service as reports

router = APIRouter(prefix="/reports", tags=["Reportes"])


@router.get("/summary", summary="Indicadores agregados del periodo (sin datos personales)")
def summary(
    ctx: Annotated[ServiceContext, Depends(require("report:read"))],
    date_from: date | None = None,
    date_to: date | None = None,
    site_id: int | None = None,
) -> dict[str, Any]:
    f = reports.resolve_filter(ctx, date_from, date_to, site_id)
    return reports.summary(ctx.db, f)


def _fmt(value: object) -> object:
    if isinstance(value, datetime):
        return value.astimezone(INSTITUTION_TZ).strftime("%d/%m/%Y %H:%M")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    return "" if value is None else value


def _stream(rows: list[dict[str, Any]], fmt: str, filename: str) -> StreamingResponse:
    headers = list(rows[0].keys()) if rows else ["sin_datos"]
    if fmt == "csv":
        buffer = io.StringIO()
        buffer.write("﻿")
        writer = csv.writer(buffer, delimiter=";")
        writer.writerow(headers)
        for row in rows:
            writer.writerow([_fmt(row[h]) for h in headers])
        return StreamingResponse(
            iter([buffer.getvalue()]),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
        )
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("Reporte")
    sheet.append(headers)
    for row in rows:
        sheet.append([_fmt(row[h]) for h in headers])
    out = io.BytesIO()
    workbook.save(out)
    out.seek(0)
    return StreamingResponse(
        out,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}.xlsx"'},
    )


@router.get("/export", summary="Exportar (Excel/CSV). El listado nominal requiere permiso adicional")
def export(
    ctx: Annotated[ServiceContext, Depends(require("report:export"))],
    report: Annotated[Literal["daily", "appointments"], Query()] = "daily",
    format: Annotated[Literal["xlsx", "csv"], Query()] = "xlsx",
    date_from: date | None = None,
    date_to: date | None = None,
    site_id: int | None = None,
) -> StreamingResponse:
    f = reports.resolve_filter(ctx, date_from, date_to, site_id)
    if report == "appointments":
        ctx.require_permission("report:read_nominal", action="REPORT_EXPORT_NOMINAL")
        rows = reports.nominal_rows(ctx.db, f)
    else:
        rows = reports.summary(ctx.db, f)["by_day"]
    ctx.audit(
        action="REPORT_EXPORT",
        resource_type="report",
        resource_id=report,
        metadata={
            "format": format,
            "date_from": f.date_from,
            "date_to": f.date_to,
            "site_ids": f.site_ids,
            "rows": len(rows),
            "nominal": report == "appointments",
        },
    )
    ctx.db.commit()
    return _stream(rows, format, f"topico_{report}_{f.date_from:%Y%m%d}_{f.date_to:%Y%m%d}")
