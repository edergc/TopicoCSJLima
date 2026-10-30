import { describe, expect, it } from "vitest";

import type { Appointment } from "@/shared/api/types";

import { consultaUrl, ticketHtml } from "./printTicket";

const appointment = {
  ticket_code: "A-015",
  site_name: "Sede Javier Alzamora Valdez",
  service_date: "2026-10-05",
  registered_at: "2026-10-05T15:18:00Z",
  people_ahead: 7,
  estimated_at: null,
  worker: { document_number: "41204384", short_name: "Carlos V. C." },
} as unknown as Appointment;

describe("ticket impreso", () => {
  it("el QR abre la consulta con DNI y turno en el fragmento (no viaja al servidor)", () => {
    expect(consultaUrl(appointment)).toBe(`${window.location.origin}/consulta#dni=41204384&turno=A-015`);
  });

  it("incluye turno, sede, nombre abreviado y un QR; escapa el HTML", () => {
    const html = ticketHtml({ ...appointment, site_name: "Sede <Prueba>" } as Appointment);
    expect(html).toContain("A-015");
    expect(html).toContain("Carlos V. C.");
    expect(html).toContain("Sede &lt;Prueba&gt;");
    expect(html).toContain("<svg");
    expect(html).not.toContain("41204384"); // el DNI solo va codificado en el QR
  });

  it("muestra la institución configurada, el logo, la prioridad y quién va primero", () => {
    const html = ticketHtml(
      { ...appointment, people_ahead: 0, priority_label: "Gestante", room_name: "Consultorio 2" } as Appointment,
      { org_name: "Poder Judicial del Perú", institution_name: "Corte <Lima>", logo_url: "/api/v1/public/branding/logo?v=1" },
    );
    expect(html).toContain("Corte &lt;Lima&gt;");
    expect(html).toContain(`<img class="logo" src="${window.location.origin}/api/v1/public/branding/logo?v=1"`);
    expect(html).toContain("Atención preferente · Gestante");
    expect(html).toContain("Ninguna: es el siguiente");
    expect(html).toContain("Consultorio 2");
  });
});
