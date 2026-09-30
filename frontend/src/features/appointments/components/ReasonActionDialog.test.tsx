import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Appointment } from "@/shared/api/types";
import { mockApi, renderWithProviders, route } from "@/test/utils";

import { ReasonActionDialog } from "./ReasonActionDialog";

const appointment = {
  public_id: "a1",
  ticket_code: "A-004",
  site_id: 1,
  version: 3,
  worker: { display_name: "ROJAS VEGA, Ana Maria", document_number: "01234567" },
} as unknown as Appointment;

const reasons = [
  { id: 1, type: "CANCEL", code: "YA_NO_REQUIERE", label: "Ya no requiere la atención", requires_note: false },
  { id: 2, type: "CANCEL", code: "OTRO", label: "Otro motivo", requires_note: true },
];

afterEach(() => vi.unstubAllGlobals());

describe("Diálogo de cancelación", () => {
  it("exige motivo, y observación si el motivo lo requiere", async () => {
    const { calls } = mockApi(route("GET", "/catalogs/reasons", reasons), route("POST", "/appointments/a1/cancel", appointment));
    const onClose = vi.fn();
    renderWithProviders(<ReasonActionDialog appointment={appointment} action="CANCEL" onClose={onClose} />);

    const confirm = await screen.findByRole("button", { name: "Cancelar atención" });
    expect(confirm).toBeDisabled();
    expect(screen.getByRole("button", { name: "Volver" })).toHaveFocus(); // la acción destructiva no es el foco

    await userEvent.click(await screen.findByLabelText("Otro motivo"));
    expect(confirm).toBeDisabled(); // falta la observación
    await userEvent.type(screen.getByLabelText(/Observación administrativa/), "Viaje por comisión");
    expect(confirm).toBeEnabled();

    await userEvent.click(confirm);
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({ reason_id: 2, note: "Viaje por comisión", version: 3 });
  });
});
