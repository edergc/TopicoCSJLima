"""Identidad visual configurable: nombres, color institucional y logo (interfaz, correos y PDF).

No se incluye el logo oficial en el código: lo carga el administrador cuando se disponga del manual
de identidad. Mientras tanto se usan la marca neutra (cruz) y el granate institucional por defecto.
"""

import html
import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleError
from app.modules.admin.parameters import get_str
from app.modules.branding.models import BrandAsset

DEFAULT_COLOR = "#7a1e2c"
MAX_LOGO_BYTES = 512 * 1024
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_SIGNATURES = {b"\x89PNG\r\n\x1a\n": "image/png", b"\xff\xd8\xff": "image/jpeg"}


@dataclass(frozen=True)
class Branding:
    org_name: str
    institution_name: str
    system_name: str
    primary_color: str
    logo_updated_at: datetime | None


def get_branding(db: Session) -> Branding:
    color = get_str(db, "branding.primary_color", DEFAULT_COLOR).strip()
    logo_updated = db.scalar(select(BrandAsset.updated_at).where(BrandAsset.code == "LOGO"))
    return Branding(
        org_name=get_str(db, "branding.org_name", "Poder Judicial del Perú"),
        institution_name=get_str(db, "institution.name", "Corte Superior de Justicia de Lima"),
        system_name=get_str(db, "institution.system_name", "Sistema de Gestión del Tópico de Salud"),
        primary_color=color.lower() if _HEX.match(color) else DEFAULT_COLOR,
        logo_updated_at=logo_updated,
    )


def get_logo(db: Session) -> BrandAsset | None:
    return db.get(BrandAsset, "LOGO")


def logo_bytes(db: Session) -> bytes | None:
    asset = get_logo(db)
    return asset.data if asset else None


def detect_image_type(data: bytes) -> str:
    """Valida por contenido (no por extensión): solo PNG o JPEG, máximo 512 KB. SVG no: puede ejecutar código."""
    if not data or len(data) > MAX_LOGO_BYTES:
        raise BusinessRuleError("LOGO_INVALID")
    for signature, mime in _SIGNATURES.items():
        if data.startswith(signature):
            return mime
    raise BusinessRuleError("LOGO_INVALID")


def email_html(body_text: str, branding: Branding) -> str:
    """Versión HTML de un correo: encabezado con el color institucional y el texto tal cual (escapado)."""
    color = branding.primary_color
    paragraphs = "".join(
        f'<p style="margin:0 0 12px">{html.escape(block).replace(chr(10), "<br>")}</p>'
        for block in body_text.strip().split("\n\n")
    )
    return f"""<!doctype html>
<html lang="es"><body style="margin:0;background:#f6f5f3;font-family:'Segoe UI',Arial,sans-serif;color:#1c1917">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f6f5f3;padding:24px 12px">
<tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #e7e5e4">
<tr><td style="background:{color};padding:18px 24px;color:#ffffff">
<div style="font-size:11px;letter-spacing:.08em;text-transform:uppercase;opacity:.85">{html.escape(branding.org_name)}</div>
<div style="font-size:16px;font-weight:600;margin-top:2px">{html.escape(branding.institution_name)}</div>
<div style="font-size:13px;opacity:.85">Tópico de Salud</div>
</td></tr>
<tr><td style="padding:24px;font-size:14px;line-height:1.55">{paragraphs}</td></tr>
</table>
</td></tr></table>
</body></html>"""
