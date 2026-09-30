import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi, route } from "@/test/utils";

import { ApiError, api, session } from "./client";

afterEach(() => {
  session.setToken(null);
  vi.unstubAllGlobals();
});

describe("cliente de la API", () => {
  it("envía el token y la cabecera anti-CSRF", async () => {
    const { fetchMock } = mockApi(route("GET", "/sites", []));
    session.setToken("abc");
    await api.get("/sites");
    const init = fetchMock.mock.calls[0]![1] as RequestInit;
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer abc");
    expect((init.headers as Record<string, string>)["X-Requested-With"]).toBe("XMLHttpRequest");
    expect(init.credentials).toBe("same-origin");
  });

  it("convierte los errores en ApiError con código estable y mensaje en español", async () => {
    mockApi(route("POST", "/appointments", { code: "CAPACITY_REACHED", message: "Se ha alcanzado la capacidad máxima…" }, 409));
    const error = await api.post("/appointments", {}).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).code).toBe("CAPACITY_REACHED");
    expect((error as ApiError).status).toBe(409);
    expect((error as ApiError).requestId).toBe("test-request");
  });

  it("renueva la sesión UNA sola vez ante varios 401 simultáneos y reintenta", async () => {
    let refreshes = 0;
    const { fetchMock } = mockApi(
      (url) => {
        if (url.pathname !== "/api/v1/auth/refresh") return undefined;
        refreshes += 1;
        return { body: { access_token: "nuevo", user: {} } };
      },
      (url, init) => {
        if (url.pathname !== "/api/v1/sites") return undefined;
        const auth = (init.headers as Record<string, string>).Authorization;
        return auth === "Bearer nuevo" ? { body: ["ok"] } : { status: 401, body: { code: "TOKEN_EXPIRED", message: "expiró" } };
      },
    );
    session.setToken("viejo");
    const results = await Promise.all([api.get("/sites"), api.get("/sites"), api.get("/sites")]);
    expect(results).toEqual([["ok"], ["ok"], ["ok"]]);
    expect(refreshes).toBe(1);
    expect(fetchMock).toHaveBeenCalledTimes(7); // 3 fallidas + 1 refresh + 3 reintentos
  });

  it("notifica la expiración cuando no se puede renovar", async () => {
    mockApi(
      route("POST", "/auth/refresh", { code: "SESSION_EXPIRED", message: "fin" }, 401),
      route("GET", "/sites", { code: "TOKEN_EXPIRED", message: "expiró" }, 401),
    );
    const onExpired = vi.fn();
    const unsubscribe = session.onExpired(onExpired);
    const error = await api.get("/sites").catch((e: unknown) => e);
    unsubscribe();
    expect((error as ApiError).code).toBe("SESSION_EXPIRED");
    expect(onExpired).toHaveBeenCalledOnce();
  });

  it("informa un error de red comprensible", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const error = await api.get("/sites").catch((e: unknown) => e);
    expect((error as ApiError).code).toBe("NETWORK_ERROR");
    expect((error as ApiError).message).toMatch(/red institucional/);
  });

  it("omite parámetros vacíos en la consulta", async () => {
    const { calls, fetchMock } = mockApi(route("GET", "/appointments", { items: [] }));
    await api.get("/appointments", { status: "", site_id: 1, document_number: undefined });
    expect(calls[0]!.path).toBe("/api/v1/appointments");
    expect(String(fetchMock.mock.calls[0]![0])).toBe("/api/v1/appointments?site_id=1");
  });
});
