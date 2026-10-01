import csv
import io
from datetime import date, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy import select

from app.core.clock import INSTITUTION_TZ
from app.modules.admin.parameters import get_str
from app.modules.auth.dependencies import ServiceContext, require
from app.modules.reports import documents
from app.modules.reports import service as reports
from app.modules.reports.documents import ReportMeta
from app.modules.reports.schemas import ReportSummaryOut
from app.modules.sites.models import Site

router = APIRouter(prefix="/reports", tags=["Reportes"])


@router.get(
    "/summary", response_model=ReportSummaryOut, summary="Indicadores agregados del periodo (sin datos personales)"
)
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


_MEDIA = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}


def _file(content: bytes, fmt: str, filename: str) -> StreamingResponse:
    return StreamingResponse(
        iter([content]),
        media_type=_MEDIA[fmt],
        headers={"Content-Disposition": f'attachment; filename="{filename}.{fmt}"'},
    )


def _meta(ctx: ServiceContext, f: reports.ReportFilter) -> ReportMeta:
    names = list(ctx.db.scalars(select(Site.name).where(Site.id.in_(f.site_ids)).order_by(Site.id)))
    return ReportMeta(
        institution=get_str(ctx.db, "institution.name", "Corte Superior de Justicia de Lima"),
        date_from=f.date_from,
        date_to=f.date_to,
        site_names=names,
        generated_at=ctx.clock.now(),
        generated_by=ctx.user.full_name,
    )


@router.get(
    "/export",
    summary="Exportar reporte (Excel, PDF o CSV)",
    description=(
        "summary: reporte de indicadores completo (Excel con varias hojas o PDF institucional). "
        "daily: detalle por día y sede. appointments: listado nominal (requiere report:export y "
        "report:read_nominal). Toda descarga queda en la auditoría."
    ),
)
def export(
    ctx: Annotated[ServiceContext, Depends(require("report:read"))],
    report: Annotated[Literal["summary", "daily", "appointments"], Query()] = "summary",
    format: Annotated[Literal["xlsx", "pdf", "csv"], Query()] = "xlsx",
    date_from: date | None = None,
    date_to: date | None = None,
    site_id: int | None = None,
) -> StreamingResponse:
    f = reports.resolve_filter(ctx, date_from, date_to, site_id)
    nominal = report == "appointments"
    if nominal:
        ctx.require_permission("report:export", action="REPORT_EXPORT_NOMINAL")
        ctx.require_permission("report:read_nominal", action="REPORT_EXPORT_NOMINAL")
        rows = reports.nominal_rows(ctx.db, f)
        count = len(rows)
    else:
        data = reports.summary(ctx.db, f)
        count = len(data["by_day"])
    ctx.audit(
        action="REPORT_EXPORT",
        resource_type="report",
        resource_id=report,
        metadata={
            "format": format,
            "date_from": f.date_from,
            "date_to": f.date_to,
            "site_ids": f.site_ids,
            "rows": count,
            "nominal": nominal,
        },
    )
    ctx.db.commit()

    name = "listado_nominal" if nominal else "reporte_topico"
    filename = f"{name}_{f.date_from:%Y%m%d}_{f.date_to:%Y%m%d}"
    if nominal:
        if format == "pdf":
            return _file(documents.nominal_pdf(rows, _meta(ctx, f)), "pdf", filename)
        return _stream(rows, format, filename)
    if format == "pdf":
        return _file(documents.summary_pdf(data, _meta(ctx, f)), "pdf", filename)
    if format == "xlsx" and report == "summary":
        return _file(documents.summary_xlsx(data, _meta(ctx, f)), "xlsx", filename)
    return _stream(data["by_day"], format, filename)
