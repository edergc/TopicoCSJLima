import qrcode from "qrcode-generator";

import type { Appointment, Branding } from "@/shared/api/types";
import { logoUrl } from "@/shared/branding/branding";
import { fmt } from "@/shared/lib/format";

const escape = (text: string) =>
  text.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);

/** Identidad institucional que encabeza el ticket (la configurada en Catálogos → Identidad visual). */
export interface TicketBrand {
  org_name: string;
  institution_name: string;
  /** Dirección del logo (relativa o absoluta); sin logo se omite. */
  logo_url?: string | null;
}

export function ticketBrand(branding: Branding): TicketBrand {
  return { org_name: branding.org_name, institution_name: branding.institution_name, logo_url: logoUrl(branding) };
}

const DEFAULT_BRAND: TicketBrand = { org_name: "Poder Judicial del Perú", institution_name: "Corte Superior de Justicia de Lima" };

const STEPS = [
  "Espere en la sala del tópico.",
  "Esté atento a la pantalla y al llamado.",
  "Al ser llamado, acérquese al consultorio indicado.",
];

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

function peopleAhead(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return value === 0 ? "Ninguna: es el siguiente" : String(value);
}

/** HTML del ticket: 80 mm de ancho (impresora térmica, en blanco y negro); en A6 u otra hoja se centra. */
export function ticketHtml(appointment: Appointment, brand: TicketBrand = DEFAULT_BRAND, printedAt: Date = new Date()): string {
  const url = consultaUrl(appointment);
  const rows: [string, string][] = [
    ["Fecha", fmt.date(appointment.service_date)],
    ["Registrado", `${fmt.time(appointment.registered_at)} h`],
    ["Personas delante", peopleAhead(appointment.people_ahead)],
    ["Hora estimada", appointment.estimated_at ? `${fmt.time(appointment.estimated_at)} h *` : "—"],
  ];
  if (appointment.room_name) rows.push(["Consultorio", appointment.room_name]);
  const logo = brand.logo_url
    ? `<img class="logo" src="${escape(new URL(brand.logo_url, window.location.origin).href)}" alt="">`
    : "";
  const priority = appointment.priority_label
    ? `<div class="prio">Atención preferente · ${escape(appointment.priority_label)}</div>`
    : "";
  return `<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>Turno ${escape(appointment.ticket_code)}</title>
<style>
  @page { size: 80mm auto; margin: 3mm; }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: "Segoe UI", Arial, sans-serif; color: #000; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  .t { width: 72mm; margin: 0 auto; text-align: center; }
  .logo { display: block; max-width: 34mm; max-height: 15mm; margin: 0 auto 2mm; filter: grayscale(1); }
  .org { font-size: 7.5pt; letter-spacing: .08em; text-transform: uppercase; }
  .inst { font-size: 9.5pt; font-weight: 700; text-transform: uppercase; line-height: 1.2; margin-top: .5mm; }
  .sub { font-size: 9pt; margin-top: .5mm; }
  .site { display: inline-block; margin-top: 2.5mm; padding: .8mm 3mm; border: 1px solid #000; border-radius: 3mm; font-size: 9pt; font-weight: 600; }
  .lbl { font-size: 8.5pt; margin-top: 4mm; letter-spacing: .3em; text-transform: uppercase; }
  .code { display: block; margin: 1.5mm 4mm 0; padding: 2mm 0 2.5mm; background: #000; color: #fff; border-radius: 3mm; font-size: 44pt; font-weight: 800; line-height: 1; letter-spacing: .02em; }
  .prio { margin: 1.5mm 4mm 0; padding: 1mm; border: 1.5px solid #000; border-radius: 2mm; font-size: 8.5pt; font-weight: 700; text-transform: uppercase; }
  .name { font-size: 10.5pt; font-weight: 700; margin-top: 2.5mm; }
  table { width: 100%; margin-top: 3mm; border-top: 1px dashed #000; border-bottom: 1px dashed #000; padding: 1.5mm 0; font-size: 9pt; border-collapse: separate; }
  td { padding: .7mm 0; text-align: left; } td:last-child { text-align: right; font-weight: 700; }
  .qr { width: 30mm; height: 30mm; margin: 3.5mm auto 1mm; }
  .qr svg { width: 100%; height: 100%; display: block; }
  .hint { font-size: 8pt; font-weight: 600; }
  ol { margin: 3mm 0 0; padding: 2mm 0 0 5mm; border-top: 1px dashed #000; text-align: left; font-size: 8.5pt; }
  li { margin: .6mm 0; }
  .foot { font-size: 7pt; margin-top: 2.5mm; line-height: 1.35; }
</style></head>
<body><div class="t">
  ${logo}
  <div class="org">${escape(brand.org_name)}</div>
  <div class="inst">${escape(brand.institution_name)}</div>
  <div class="sub">Tópico de Salud</div>
  <div class="site">${escape(appointment.site_name)}</div>
  <div class="lbl">Su turno</div>
  <div class="code">${escape(appointment.ticket_code)}</div>
  ${priority}
  <div class="name">${escape(appointment.worker.short_name)}</div>
  <table>${rows.map(([k, v]) => `<tr><td>${k}</td><td>${escape(v)}</td></tr>`).join("")}</table>
  <div class="qr">${qrSvg(url)}</div>
  <div class="hint">Escanee para seguir su turno en el celular</div>
  <ol>${STEPS.map((s) => `<li>${s}</li>`).join("")}</ol>
  <div class="foot">* La hora estimada es referencial y cambia según avanza la atención.<br>Impreso: ${escape(fmt.dateTime(printedAt))} · Conserve este ticket.</div>
</div></body></html>`;
}

/** Imprime el ticket con un marco oculto (no abre ventanas emergentes); espera a que cargue el logo. */
export function printTicket(appointment: Appointment, brand?: TicketBrand): void {
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
  doc.write(ticketHtml(appointment, brand));
  doc.close();
  const win = frame.contentWindow;
  const cleanup = () => window.setTimeout(() => frame.remove(), 1000);
  win.addEventListener("afterprint", cleanup, { once: true });
  const images = Array.from(doc.images).map((img) =>
    img.complete ? Promise.resolve() : new Promise<void>((done) => {
          img.addEventListener("load", () => done(), { once: true });
          img.addEventListener("error", () => done(), { once: true });
        }),
  );
  // Un logo que no carga (o tarda) no debe impedir imprimir: como máximo se espera 2 s.
  void Promise.race([Promise.all(images), new Promise((done) => window.setTimeout(done, 2000))]).then(() => {
    win.focus();
    win.print();
    window.setTimeout(cleanup, 60_000); // por si el navegador no emite "afterprint"
  });
}
