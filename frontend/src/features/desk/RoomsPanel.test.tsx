import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { RoomStatus } from "@/shared/api/types";

import { RoomsPanel } from "./RoomsPanel";

const rooms: RoomStatus[] = [
  {
    id: 1,
    name: "Consultorio 1",
    location_note: null,
    status: "IN_SERVICE",
    ticket_code: "A-004",
    worker_name: "Juan Pérez",
    doctor_name: "Dra. Medina",
    since: new Date().toISOString(),
  },
  { id: 2, name: "Consultorio 2", location_note: null, status: "FREE" },
  { id: 3, name: "Consultorio 3", location_note: null, status: "FREE" },
];

describe("panel de consultorios", () => {
  it("muestra quién ocupa cada consultorio y adónde va el próximo llamado", () => {
    render(<RoomsPanel rooms={rooms} targetId={2} onTarget={() => {}} />);
    expect(screen.getByText("En atención")).toBeInTheDocument();
    expect(screen.getByText(/Juan Pérez/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Consultorio 2/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("El próximo llamado viene aquí")).toBeInTheDocument();
    // Un consultorio ocupado no se puede elegir como destino
    expect(screen.queryByRole("button", { name: /Consultorio 1/ })).toBeNull();
  });

  it("permite elegir otro consultorio libre", () => {
    const onTarget = vi.fn();
    render(<RoomsPanel rooms={rooms} targetId={2} onTarget={onTarget} />);
    fireEvent.click(screen.getByRole("button", { name: /Consultorio 3/ }));
    expect(onTarget).toHaveBeenCalledWith(3);
  });
});
