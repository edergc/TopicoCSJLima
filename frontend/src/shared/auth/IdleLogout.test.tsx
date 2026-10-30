import { act, fireEvent, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/test/utils";

import { IdleLogout, LAST_ACTIVITY_KEY } from "./IdleLogout";

const logout = vi.fn(() => Promise.resolve());
let idleMinutes = 2;

vi.mock("@/shared/auth/AuthProvider", () => ({
  useAuth: () => ({ logout }),
  useUser: () => ({ idle_timeout_minutes: idleMinutes }),
}));

describe("Cierre de sesión por inactividad", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    logout.mockClear();
    localStorage.removeItem(LAST_ACTIVITY_KEY);
    idleMinutes = 2;
  });
  afterEach(() => vi.useRealTimers());

  const advance = (ms: number) => act(() => vi.advanceTimersByTime(ms));

  it("avisa un minuto antes y cierra la sesión al cumplirse el tiempo", async () => {
    renderWithProviders(<IdleLogout />);
    advance(59_000);
    expect(screen.queryByText("¿Sigue ahí?")).not.toBeInTheDocument();
    advance(2_000);
    expect(screen.getByText("¿Sigue ahí?")).toBeInTheDocument();
    // Mover el mouse con el aviso abierto no basta: hay que confirmar
    fireEvent.pointerMove(window);
    advance(60_000);
    expect(logout).toHaveBeenCalledTimes(1);
  });

  it("«Seguir conectado» y el uso normal mantienen la sesión", () => {
    renderWithProviders(<IdleLogout />);
    advance(50_000);
    fireEvent.keyDown(window, { key: "a" }); // uso normal antes del aviso
    advance(50_000);
    expect(screen.queryByText("¿Sigue ahí?")).not.toBeInTheDocument();
    advance(20_000);
    fireEvent.click(screen.getByRole("button", { name: "Seguir conectado" }));
    advance(30_000);
    expect(screen.queryByText("¿Sigue ahí?")).not.toBeInTheDocument();
    expect(logout).not.toHaveBeenCalled();
  });

  it("la actividad en otra pestaña también cuenta", () => {
    renderWithProviders(<IdleLogout />);
    advance(90_000);
    localStorage.setItem(LAST_ACTIVITY_KEY, String(Date.now()));
    advance(1_000);
    expect(screen.queryByText("¿Sigue ahí?")).not.toBeInTheDocument();
  });

  it("con 0 minutos no cierra nunca", () => {
    idleMinutes = 0;
    renderWithProviders(<IdleLogout />);
    advance(10 * 60 * 60_000);
    expect(logout).not.toHaveBeenCalled();
  });
});
