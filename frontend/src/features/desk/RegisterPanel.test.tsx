import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi, renderWithProviders, route } from "@/test/utils";

import { RegisterPanel } from "./RegisterPanel";

vi.mock("@/shared/auth/AuthProvider", () => ({
  useAuth: () => ({ can: () => true }),
}));

const worker = {
  public_id: "w1",
  document_type: "DNI",
  document_number: "01234567",
  first_names: "ANA MARIA",
  paternal_surname: "ROJAS",
  maternal_surname: "VEGA",
  department_name: "MESA DE PARTES ÚNICA",
  has_email: false,
  has_phone: true,
  is_active: true,
};

const availability = {
  site_id: 1,
  service_date: "2026-09-29",
  capacity: 20,
  occupied: 5,
  available: 15,
  day_status: "OPEN",
  can_register: true,
  blocker_code: null,
  blocker_message: null,
  blocks: [],
  closure_reason: null,
};

afterEach(() => vi.unstubAllGlobals());

describe("Panel de registro por DNI", () => {
  it("acepta solo dígitos y consulta al completar 8", async () => {
    const { calls } = mockApi(
      route("GET", "/workers/eligibility", {
        document_number: "01234567",
        found: true,
        eligible: true,
        code: null,
        message: "ok",
        worker,
        coverage: null,
        active_appointment: null,
      }),
    );
    renderWithProviders(<RegisterPanel siteId={1} availability={availability} onRegistered={vi.fn()} />);
    const input = screen.getByLabelText("DNI del trabajador");
    await userEvent.type(input, "0123a45-67");
    expect(input).toHaveValue("01234567");
    expect(await screen.findByText("Habilitado · EPS Rímac vigente")).toBeInTheDocument();
    expect(screen.getByText(/ROJAS VEGA, ANA MARIA/)).toBeInTheDocument();
    expect(screen.getByText(/Sin correo: no recibirá notificaciones/)).toBeInTheDocument();
    expect(calls.some((c) => c.path === "/api/v1/workers/eligibility")).toBe(true);
  });

  it("no permite registrar a un trabajador no habilitado (caso 7)", async () => {
    mockApi(
      route("GET", "/workers/eligibility", {
        document_number: "01234567",
        found: true,
        eligible: false,
        code: "WORKER_NOT_ELIGIBLE",
        message: "El trabajador no cuenta con cobertura EPS Rímac vigente.",
        worker,
        coverage: null,
        active_appointment: null,
      }),
    );
    renderWithProviders(<RegisterPanel siteId={1} availability={availability} onRegistered={vi.fn()} />);
    await userEvent.type(screen.getByLabelText("DNI del trabajador"), "01234567");
    expect(await screen.findByText("El trabajador no cuenta con cobertura EPS Rímac vigente.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Registrar turno/ })).toBeDisabled();
  });

  it("registra con el canal elegido y reinicia el campo", async () => {
    const onRegistered = vi.fn();
    const { calls } = mockApi(
      route("GET", "/workers/eligibility", {
        document_number: "01234567",
        found: true,
        eligible: true,
        code: null,
        message: "ok",
        worker,
        coverage: null,
        active_appointment: null,
      }),
      route("POST", "/appointments", { ticket_code: "A-015", public_id: "a1" }, 201),
    );
    renderWithProviders(<RegisterPanel siteId={1} availability={availability} onRegistered={onRegistered} />);
    const input = screen.getByLabelText("DNI del trabajador");
    await userEvent.type(input, "01234567");
    await screen.findByText("Habilitado · EPS Rímac vigente");
    await userEvent.click(screen.getByRole("radio", { name: "Presencial" }));
    await userEvent.click(screen.getByRole("button", { name: /Registrar turno/ }));
    await waitFor(() => expect(onRegistered).toHaveBeenCalledWith(expect.objectContaining({ ticket_code: "A-015" })));
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({
      site_id: 1,
      document_number: "01234567",
      channel: "WALK_IN",
      admin_note: null,
    });
    expect(input).toHaveValue("");
  });

  it("muestra el bloqueo por capacidad agotada (caso 1)", async () => {
    mockApi(
      route("GET", "/workers/eligibility", {
        document_number: "01234567",
        found: true,
        eligible: true,
        code: null,
        message: "ok",
        worker,
        coverage: null,
        active_appointment: null,
      }),
    );
    const full = {
      ...availability,
      available: 0,
      can_register: false,
      blocker_code: "CAPACITY_REACHED",
      blocker_message: "Se ha alcanzado la capacidad máxima de atención para esta sede en la fecha seleccionada.",
    };
    renderWithProviders(<RegisterPanel siteId={1} availability={full} onRegistered={vi.fn()} />);
    await userEvent.type(screen.getByLabelText("DNI del trabajador"), "01234567");
    expect(await screen.findByText(/capacidad máxima de atención/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Registrar turno/ })).toBeDisabled();
  });
});
