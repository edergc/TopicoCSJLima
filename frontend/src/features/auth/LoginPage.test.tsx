import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "@/shared/auth/AuthProvider";
import { mockApi, renderWithProviders, route } from "@/test/utils";

import LoginPage from "./LoginPage";

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("Inicio de sesión", () => {
  it("cada etiqueta queda asociada a su campo (también los que llevan ícono)", async () => {
    mockApi(route("POST", "/auth/refresh", { code: "UNAUTHORIZED", message: "" }, 401));
    renderWithProviders(
      <AuthProvider>
        <LoginPage />
      </AuthProvider>,
    );

    const user = await screen.findByLabelText("Usuario", { selector: "input" });
    expect(user).toHaveAttribute("autocomplete", "username");
    expect(screen.getByLabelText("Contraseña", { selector: "input" })).toHaveAttribute("autocomplete", "current-password");
    expect(screen.getByRole("checkbox", { name: /recordar mi usuario/i })).not.toBeChecked();
  });

  it("recuerda solo el usuario guardado en este equipo", async () => {
    localStorage.setItem("topico.lastUser", "40000003");
    mockApi(route("POST", "/auth/refresh", { code: "UNAUTHORIZED", message: "" }, 401));
    renderWithProviders(
      <AuthProvider>
        <LoginPage />
      </AuthProvider>,
    );

    expect(await screen.findByLabelText("Usuario", { selector: "input" })).toHaveValue("40000003");
    expect(screen.getByRole("checkbox", { name: /recordar mi usuario/i })).toBeChecked();
  });
});
