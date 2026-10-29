import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

    const user = await screen.findByLabelText("Usuario (DNI)", { selector: "input" });
    expect(user).toHaveAttribute("autocomplete", "username");
    expect(screen.getByLabelText("Contraseña", { selector: "input" })).toHaveAttribute("autocomplete", "current-password");
    expect(screen.getByRole("checkbox", { name: /recordar mi usuario/i })).not.toBeChecked();
  });

  it("el usuario es el DNI: solo 8 dígitos, sin letras (admite ceros)", async () => {
    mockApi(route("POST", "/auth/refresh", { code: "UNAUTHORIZED", message: "" }, 401));
    renderWithProviders(
      <AuthProvider>
        <LoginPage />
      </AuthProvider>,
    );
    const user = await screen.findByLabelText("Usuario (DNI)", { selector: "input" });
    await userEvent.type(user, "admin0012a3450999");
    expect(user).toHaveValue("00123450");
  });

  it("recuerda solo el usuario guardado en este equipo", async () => {
    localStorage.setItem("topico.lastUser", "40000003");
    mockApi(route("POST", "/auth/refresh", { code: "UNAUTHORIZED", message: "" }, 401));
    renderWithProviders(
      <AuthProvider>
        <LoginPage />
      </AuthProvider>,
    );

    expect(await screen.findByLabelText("Usuario (DNI)", { selector: "input" })).toHaveValue("40000003");
    expect(screen.getByRole("checkbox", { name: /recordar mi usuario/i })).toBeChecked();
  });
});
