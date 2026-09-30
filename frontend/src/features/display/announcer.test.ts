import { describe, expect, it } from "vitest";

import { announcementText } from "./announcer";

describe("announcementText", () => {
  it("lee el turno como letra + número y el nombre sin puntos de abreviatura", () => {
    expect(announcementText("A-047", "María G.", "al tópico")).toBe("Turno A 47. María G. Por favor, acérquese al tópico.");
  });

  it("omite el nombre cuando la pantalla no muestra nombres", () => {
    expect(announcementText("B-005", null, "al tópico")).toBe("Turno B 5. Por favor, acérquese al tópico.");
  });
});
