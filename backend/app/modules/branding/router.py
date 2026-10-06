"""Identidad visual: lectura pública (interfaz, pantalla de sala) y carga del logo (administración)."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Response, UploadFile
from sqlalchemy import delete

from app.core.errors import NotFoundError
from app.modules.auth.dependencies import DbDep, ServiceContext, require
from app.modules.branding import service as branding
from app.modules.branding.models import BrandAsset
from app.shared.schemas import ApiOut

public_router = APIRouter(prefix="/public/branding", tags=["Identidad visual"])
admin_router = APIRouter(prefix="/admin/branding", tags=["Identidad visual"])

ManageCtx = Annotated[ServiceContext, Depends(require("parameter:manage"))]


class BrandingOut(ApiOut):
    org_name: str
    institution_name: str
    system_name: str
    primary_color: str
    logo_updated_at: datetime | None


@public_router.get("", response_model=BrandingOut, summary="Nombres, color institucional y versión del logo")
def get_branding(db: DbDep) -> branding.Branding:
    return branding.get_branding(db)


@public_router.get("/logo", summary="Logo institucional (PNG/JPEG)")
def get_logo(db: DbDep) -> Response:
    asset = branding.get_logo(db)
    if asset is None:
        raise NotFoundError()
    return Response(
        content=asset.data,
        media_type=asset.content_type,
        # La URL incluye ?v=<fecha de actualización>: se puede guardar en caché sin quedar desactualizada.
        headers={"Cache-Control": "public, max-age=86400", "X-Content-Type-Options": "nosniff"},
    )


@admin_router.put("/logo", response_model=BrandingOut, summary="Cargar o reemplazar el logo (PNG/JPEG, máx. 512 KB)")
def upload_logo(
    ctx: ManageCtx, file: Annotated[UploadFile, File(description="Logo PNG o JPEG")]
) -> branding.Branding:
    data = file.file.read(branding.MAX_LOGO_BYTES + 1)
    mime = branding.detect_image_type(data)
    asset = ctx.db.get(BrandAsset, "LOGO")
    if asset is None:
        ctx.db.add(BrandAsset(code="LOGO", content_type=mime, data=data, updated_by=ctx.user.id))
    else:
        asset.content_type, asset.data, asset.updated_by = mime, data, ctx.user.id
        asset.updated_at = ctx.clock.now()
    ctx.audit(
        action="BRANDING_LOGO_UPDATE",
        resource_type="brand_asset",
        resource_id="LOGO",
        after={"content_type": mime, "bytes": len(data), "file_name": (file.filename or "")[:100]},
    )
    ctx.db.commit()
    return branding.get_branding(ctx.db)


@admin_router.delete("/logo", status_code=204, summary="Quitar el logo (vuelve a la marca por defecto)")
def delete_logo(ctx: ManageCtx) -> Response:
    ctx.db.execute(delete(BrandAsset).where(BrandAsset.code == "LOGO"))
    ctx.audit(action="BRANDING_LOGO_DELETE", resource_type="brand_asset", resource_id="LOGO")
    ctx.db.commit()
    return Response(status_code=204)
