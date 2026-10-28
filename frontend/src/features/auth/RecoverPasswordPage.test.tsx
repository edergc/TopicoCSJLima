import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi, renderWithProviders, route } from "@/test/utils";

import RecoverPasswordPage from "./RecoverPasswordPage";

afterEach(() => {
  vi.unstubAllGlobals();
  window.history.replaceState(null, "", "/");
});

describe("Recuperar contraseña", () => {
  it("pide el enlace por usuario y muestra la misma respuesta exista o no", async () => {
    const { calls } = mockApi(route("POST", "/auth/password-reset/request", undefined, 204));
    renderWithProviders(<RecoverPasswordPage />);

    await userEvent.type(screen.getByLabelText("Usuario"), "40000003");
    await userEvent.click(screen.getByRole("button", { name: /enviar enlace/i }));

    expect(await screen.findByText("Revise su correo")).toBeInTheDocument();
    expect(calls.find((c) => c.path.endsWith("/password-reset/request"))?.body).toEqual({ username: "40000003" });
  });

  it("con el enlace del correo define la nueva contraseña y avisa si el enlace venció", async () => {
    window.history.replaceState(null, "", "/recuperar-clave#token-de-prueba-123456");
    const { calls } = mockApi(
      route("POST", "/auth/password-reset/confirm", { code: "RESET_LINK_EXPIRED", message: "El enlace venció." }, 422),
    );
    renderWithProviders(<RecoverPasswordPage />);
    expect(window.location.hash).toBe(""); // el token no queda en la barra de direcciones

    await userEvent.type(screen.getByLabelText("Nueva contraseña"), "NuevaClave2026");
    await userEvent.type(screen.getByLabelText("Confirmar nueva contraseña"), "NuevaClave2026");
    await userEvent.click(screen.getByRole("button", { name: /guardar contraseña/i }));

    await waitFor(() => expect(screen.getByText("Enlace no válido")).toBeInTheDocument());
    expect(calls.find((c) => c.path.endsWith("/password-reset/confirm"))?.body).toEqual({
      token: "token-de-prueba-123456",
      new_password: "NuevaClave2026",
    });
    await userEvent.click(screen.getByRole("button", { name: /solicitar un nuevo enlace/i }));
    expect(screen.getByRole("button", { name: /enviar enlace/i })).toBeInTheDocument();
  });
});
