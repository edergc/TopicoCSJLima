import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { importFresh, isStaleChunkError } from "./staleVersion";

describe("Pestaña con una versión anterior del sistema", () => {
  const reload = vi.fn();

  beforeEach(() => {
    sessionStorage.clear();
    reload.mockClear();
    vi.stubGlobal("location", { ...window.location, reload });
  });
  afterEach(() => vi.unstubAllGlobals());

  it("reconoce el error de un archivo que ya no existe (Chrome, Firefox, Safari)", () => {
    expect(isStaleChunkError(new TypeError("Failed to fetch dynamically imported module: /assets/DeskPage-abc.js"))).toBe(true);
    expect(isStaleChunkError(new TypeError("error loading dynamically imported module"))).toBe(true);
    expect(isStaleChunkError(new TypeError("Importing a module script failed."))).toBe(true);
    expect(isStaleChunkError(new Error("Cannot read properties of undefined"))).toBe(false);
  });

  it("recarga una sola vez; si vuelve a fallar enseguida, muestra el error", async () => {
    const missing = () => Promise.reject(new TypeError("Failed to fetch dynamically imported module"));
    void importFresh(missing); // queda pendiente: la página se recarga
    await Promise.resolve();
    await Promise.resolve();
    expect(reload).toHaveBeenCalledTimes(1);
    await expect(importFresh(missing)).rejects.toThrow("dynamically imported module");
    expect(reload).toHaveBeenCalledTimes(1);
  });

  it("otros errores no recargan", async () => {
    await expect(importFresh(() => Promise.reject(new Error("fallo de código")))).rejects.toThrow("fallo de código");
    expect(reload).not.toHaveBeenCalled();
  });
});
