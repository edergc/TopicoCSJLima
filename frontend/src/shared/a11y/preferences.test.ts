import { afterEach, describe, expect, it } from "vitest";

import { brandScale } from "@/shared/branding/branding";

import { setA11y } from "./preferences";

describe("preferencias de accesibilidad", () => {
  afterEach(() => setA11y({ scale: 1, contrast: false }));

  it("aplica alto contraste y tamaño de letra, y los recuerda en el equipo", () => {
    setA11y({ contrast: true, scale: 1.25 });
    expect(document.documentElement.dataset.contrast).toBe("high");
    expect(document.documentElement.style.fontSize).toBe("125%");
    expect(JSON.parse(localStorage.getItem("topico.a11y")!)).toEqual({ scale: 1.25, contrast: true });

    setA11y({ contrast: false, scale: 1 });
    expect(document.documentElement.dataset.contrast).toBeUndefined();
    expect(document.documentElement.style.fontSize).toBe("");
  });
});

describe("escala de la marca", () => {
  it("usa el color institucional como tono principal y deriva los demás", () => {
    const scale = brandScale("#123456");
    expect(scale["--color-brand-700"]).toBe("#123456");
    expect(scale["--color-brand-50"]).toContain("white");
    expect(scale["--color-brand-900"]).toContain("black");
  });
});
