import qrcode from "qrcode-generator";

import type { Appointment } from "@/shared/api/types";
import { fmt } from "@/shared/lib/format";

const escape = (text: string) =>
  text.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);

/**
 * Dirección de la consulta con el DNI y el turno ya cargados.
 * Van en el fragmento (#…), que el navegador no envía al servidor: no quedan en los registros de acceso.
 */
export function consultaUrl(appointment: Appointment): string {
  const params = new URLSearchParams({ dni: appointment.worker.document_number, turno: appointment.ticket_code });
  return `${window.location.origin}/consulta#${params.toString()}`;
}

function qrSvg(text: string): string {
  const qr = qrcode(0, "M");
  qr.addData(text);
  qr.make();
  return qr.createSvgTag({ cellSize: 4, margin: 0, scalable: true });
}

/** HTML del ticket: 80 mm de ancho (impresora térmica); en A6 u otra hoja se centra. */
export function ticketHtml(appointment: Appointment): string {
  const url = consultaUrl(appointment);
  const rows = [
    ["Fecha", fmt.date(appointment.service_date)],
    ["Registrado", fmt.time(appointment.registered_at)],
    ["Personas delante", appointment.people_ahead ?? "—"],
    ["Hora estimada", appointment.estimated_at ? fmt.time(appointment.estimated_at) : "—"],
  ];
  return `<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>Turno ${escape(appointment.ticket_code)}</title>
<style>
  @page { size: 80mm auto; margin: 3mm; }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: "Segoe UI", Arial, sans-serif; color: #000; }
  .t { width: 72mm; margin: 0 auto; text-align: center; }
  .inst { font-size: 9pt; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; }
  .sub { font-size: 9pt; margin-top: 1mm; }
  .site { font-size: 10pt; font-weight: 600; margin-top: 2mm; }
  .lbl { font-size: 9pt; margin-top: 4mm; letter-spacing: .2em; text-transform: uppercase; }
  .code { font-size: 40pt; font-weight: 800; line-height: 1; margin: 1mm 0 2mm; }
  .name { font-size: 10pt; font-weight: 600; }
  table { width: 100%; margin-top: 3mm; border-top: 1px dashed #000; border-bottom: 1px dashed #000; padding: 2mm 0; font-size: 9pt; }
  td { padding: .6mm 0; } td:last-child { text-align: right; font-weight: 600; }
  .qr { width: 30mm; height: 30mm; margin: 3mm auto 1mm; }
  .qr svg { width: 100%; height: 100%; }
  .hint { font-size: 8pt; }
  .foot { font-size: 7.5pt; margin-top: 3mm; }
</style></head>
<body><div class="t">
  <div class="inst">Corte Superior de Justicia de Lima</div>
  <div class="sub">Tópico de Salud</div>
  <div class="site">${escape(appointment.site_name)}</div>
  <div class="lbl">Su turno</div>
  <div class="code">${escape(appointment.ticket_code)}</div>
  <div class="name">${escape(appointment.worker.short_name)}</div>
  <table>${rows.map(([k, v]) => `<tr><td>${k}</td><td>${escape(String(v))}</td></tr>`).join("")}</table>
  <div class="qr">${qrSvg(url)}</div>
  <div class="hint">Escanee para ver su turno en el celular</div>
  <div class="foot">Esté atento al llamado en la pantalla de la sala. La hora estimada es referencial.</div>
</div></body></html>`;
}

/** Imprime el ticket con un marco oculto (no abre ventanas emergentes). */
export function printTicket(appointment: Appointment): void {
  const frame = document.createElement("iframe");
  frame.setAttribute("aria-hidden", "true");
  Object.assign(frame.style, { position: "fixed", right: "0", bottom: "0", width: "0", height: "0", border: "0" });
  document.body.append(frame);
  const doc = frame.contentDocument;
  if (!doc || !frame.contentWindow) {
    frame.remove();
    return;
  }
  doc.open();
  doc.write(ticketHtml(appointment));
  doc.close();
  const win = frame.contentWindow;
  const cleanup = () => window.setTimeout(() => frame.remove(), 1000);
  win.addEventListener("afterprint", cleanup, { once: true });
  window.setTimeout(() => {
    win.focus();
    win.print();
    window.setTimeout(cleanup, 60_000); // por si el navegador no emite "afterprint"
  }, 150);
}
