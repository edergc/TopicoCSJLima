"""Ticket digital del turno: correo con el ticket (HTML) y el mismo ticket en PDF adjunto, con QR.

El QR y el botón abren la consulta pública con el DNI y el turno ya cargados. Van en el fragmento
(#…), que el navegador no envía al servidor: no quedan en los registros de acceso.
"""

import html
import io
from typing import Any
from urllib.parse import urlencode

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

from app.modules.branding.service import Branding

STEPS = (
    "Diríjase a la sala de espera del tópico.",
    "Esté atento a la pantalla y al llamado de su turno.",
    "Cuando lo llamen, acérquese al consultorio indicado.",
)


def status_link(base_url: str, document_number: str, ticket_code: str) -> str:
    """Consulta pública del turno con los datos precargados (o "" si no hay dirección pública configurada)."""
    if not base_url:
        return ""
    return f"{base_url.rstrip('/')}#{urlencode({'dni': document_number, 'turno': ticket_code})}"


def _rows(context: dict[str, Any]) -> list[tuple[str, str]]:
    rows = [("Sede", context["site_name"]), ("Fecha", context["service_date"])]
    rows.append(("Registrado", f"{context['registered_time']} h"))
    if context.get("people_ahead") not in ("", None):
        ahead = int(context["people_ahead"])
        rows.append(("Personas delante", "Ninguna, es el siguiente" if ahead == 0 else str(ahead)))
    if context.get("estimated_time"):
        rows.append(("Hora estimada", f"{context['estimated_time']} h (referencial)"))
    return rows


# ------------------------------------------------------------------------------------------- correo
def ticket_email_html(intro_text: str, context: dict[str, Any], brand: Branding) -> str:
    """Correo con el saludo de la plantilla (editable por el administrador) seguido del ticket."""
    e = html.escape
    color = brand.primary_color
    # Del texto de la plantilla se toma el saludo: los párrafos anteriores al que menciona el turno
    # (ese y los siguientes repiten los datos que ya muestra el ticket).
    blocks = [b for b in intro_text.strip().split("\n\n") if b.strip()]
    greeting: list[str] = []
    for block in blocks:
        if context["ticket_code"] in block:
            break
        greeting.append(block)
    intro = "".join(
        f'<p style="margin:0 0 12px">{e(block).replace(chr(10), "<br>")}</p>' for block in (greeting or blocks[:1])
    )
    rows = "".join(
        f'<tr><td style="padding:7px 0;color:#57534e;font-size:13px;border-bottom:1px solid #f0eeec">{e(k)}</td>'
        f'<td align="right" style="padding:7px 0;font-size:14px;font-weight:600;border-bottom:1px solid #f0eeec">'
        f"{e(v)}</td></tr>"
        for k, v in _rows(context)
    )
    link = context.get("status_link") or ""
    button = (
        f'<tr><td align="center" style="padding:4px 24px 22px">'
        f'<a href="{e(link)}" style="display:inline-block;background:{color};color:#ffffff;text-decoration:none;'
        f'font-weight:600;font-size:15px;padding:12px 26px;border-radius:8px">Ver mi turno en tiempo real</a>'
        f'<div style="font-size:12px;color:#78716c;margin-top:8px">Funciona desde el celular, en la red de la Corte.</div>'
        f"</td></tr>"
        if link
        else ""
    )
    steps = "".join(
        f'<tr><td valign="top" style="padding:4px 10px 4px 0"><span style="display:inline-block;width:22px;height:22px;'
        f"line-height:22px;border-radius:11px;background:{color};color:#fff;font-size:12px;font-weight:700;"
        f'text-align:center">{i}</span></td><td style="padding:4px 0;font-size:13px;color:#44403c">{e(s)}</td></tr>'
        for i, s in enumerate(STEPS, 1)
    )
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Turno {e(context["ticket_code"])}</title></head>
<body style="margin:0;background:#f6f5f3;font-family:'Segoe UI',Arial,sans-serif;color:#1c1917">
<div style="display:none;max-height:0;overflow:hidden">Su turno es el {e(context["ticket_code"])} · {e(context["site_name"])}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f6f5f3;padding:24px 12px">
<tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px">
<tr><td style="background:{color};padding:18px 24px;color:#ffffff;border-radius:12px 12px 0 0">
<div style="font-size:11px;letter-spacing:.08em;text-transform:uppercase;opacity:.85">{e(brand.org_name)}</div>
<div style="font-size:16px;font-weight:600;margin-top:2px">{e(brand.institution_name)}</div>
<div style="font-size:13px;opacity:.85">Tópico de Salud</div>
</td></tr>
<tr><td style="background:#ffffff;padding:22px 24px 6px;font-size:14px;line-height:1.55;border-left:1px solid #e7e5e4;border-right:1px solid #e7e5e4">{intro}</td></tr>
<tr><td style="background:#ffffff;padding:0 24px;border-left:1px solid #e7e5e4;border-right:1px solid #e7e5e4">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:2px dashed {color};border-radius:12px">
<tr><td align="center" style="padding:18px 16px 6px">
<div style="font-size:11px;letter-spacing:.25em;text-transform:uppercase;color:#57534e">Su turno</div>
<div style="font-size:52px;line-height:1.05;font-weight:800;color:{color};letter-spacing:.02em;margin:4px 0">{e(context["ticket_code"])}</div>
<div style="font-size:14px;font-weight:600">{e(context.get("worker_name", ""))}</div>
</td></tr>
<tr><td style="padding:8px 20px 14px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rows}</table>
</td></tr>
</table>
</td></tr>
<tr><td style="background:#ffffff;padding:18px 0 0;border-left:1px solid #e7e5e4;border-right:1px solid #e7e5e4">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{button}</table>
</td></tr>
<tr><td style="background:#ffffff;padding:0 24px 20px;border-left:1px solid #e7e5e4;border-right:1px solid #e7e5e4">
<div style="font-size:13px;font-weight:600;margin-bottom:6px">Qué hacer ahora</div>
<table role="presentation" cellpadding="0" cellspacing="0">{steps}</table>
<div style="font-size:12px;color:#78716c;margin-top:12px">Adjuntamos el ticket en PDF con un código QR: puede mostrarlo en el celular o imprimirlo.</div>
</td></tr>
<tr><td style="background:#fafaf9;padding:14px 24px;font-size:11px;color:#78716c;border:1px solid #e7e5e4;border-top:0;border-radius:0 0 12px 12px">
Este es un mensaje automático; por favor no responda a este correo. Si ya no requiere la atención, comuníquese con el tópico para liberar el cupo.
</td></tr>
</table>
</td></tr></table>
</body></html>"""


# ---------------------------------------------------------------------------------------------- PDF
def ticket_pdf(context: dict[str, Any], brand: Branding, logo: bytes | None) -> bytes:
    """Ticket de 80 × 146 mm (formato de ticket; se ve bien en el celular y se puede imprimir)."""
    width, height = 80 * mm, 146 * mm
    out = io.BytesIO()
    c = Canvas(out, pagesize=(width, height))
    c.setTitle(f"Turno {context['ticket_code']}")
    c.setAuthor(brand.institution_name)
    color = colors.HexColor(brand.primary_color)
    cx = width / 2

    # Encabezado con el color institucional
    head = 26 * mm
    c.setFillColor(color)
    c.rect(0, height - head, width, head, stroke=0, fill=1)
    text_y = height - 9 * mm
    if logo:
        try:
            image = ImageReader(io.BytesIO(logo))
            iw, ih = image.getSize()
            h = 9 * mm
            w = min(h * iw / ih, 30 * mm)
            c.setFillColor(colors.white)
            c.roundRect(cx - w / 2 - 1.5 * mm, height - 12.5 * mm, w + 3 * mm, h + 2 * mm, 1.5 * mm, stroke=0, fill=1)
            c.drawImage(image, cx - w / 2, height - 11.5 * mm, width=w, height=h, mask="auto")
            text_y = height - 17 * mm
        except Exception:  # un logo dañado no impide el ticket
            text_y = height - 9 * mm
    c.setFillColor(colors.white)
    c.setFont("Helvetica", 6.5)
    c.drawCentredString(cx, text_y, brand.org_name.upper())
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(cx, text_y - 3.6 * mm, brand.institution_name.upper()[:48])
    c.setFont("Helvetica", 7.5)
    c.drawCentredString(cx, text_y - 7 * mm, "Tópico de Salud")

    # Turno
    y = height - head - 9 * mm
    c.setFillColor(colors.HexColor("#57534e"))
    c.setFont("Helvetica", 7.5)
    c.drawCentredString(cx, y, "S U   T U R N O")
    c.setFillColor(color)
    c.setFont("Helvetica-Bold", 40)
    c.drawCentredString(cx, y - 15 * mm, context["ticket_code"])
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(cx, y - 21 * mm, str(context.get("worker_name", ""))[:40])

    # Datos
    y -= 27 * mm
    c.setStrokeColor(colors.HexColor("#a8a29e"))
    c.setDash(2, 2)
    c.line(6 * mm, y, width - 6 * mm, y)
    y -= 5 * mm
    for label, value in _rows(context):
        c.setFont("Helvetica", 8)
        c.setFillColor(colors.HexColor("#57534e"))
        c.drawString(6 * mm, y, label)
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(colors.black)
        c.drawRightString(width - 6 * mm, y, str(value)[:34])
        y -= 4.6 * mm
    c.line(6 * mm, y + 1.5 * mm, width - 6 * mm, y + 1.5 * mm)
    c.setDash()

    # QR
    link = context.get("status_link") or ""
    if link:
        size = 30 * mm
        widget = QrCodeWidget(link, barLevel="M")
        x1, y1, x2, y2 = widget.getBounds()
        drawing = Drawing(size, size, transform=[size / (x2 - x1), 0, 0, size / (y2 - y1), 0, 0])
        drawing.add(widget)
        y -= size + 2 * mm
        renderPDF.draw(drawing, c, cx - size / 2, y)
        c.setFont("Helvetica", 7)
        c.setFillColor(colors.HexColor("#44403c"))
        c.drawCentredString(cx, y - 3.5 * mm, "Escanee para ver su turno en tiempo real")
        y -= 8 * mm

    # Indicaciones
    c.setFont("Helvetica", 6.8)
    c.setFillColor(colors.HexColor("#57534e"))
    for line in ("Esté atento al llamado en la pantalla de la sala.", "La hora estimada es referencial."):
        c.drawCentredString(cx, y, line)
        y -= 3.4 * mm
    c.showPage()
    c.save()
    return out.getvalue()
