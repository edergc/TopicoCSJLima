import { describe, expect, it } from "vitest";

import { addDaysIso, countdown, fmt, minutesSince, todayIso } from "./format";

describe("formato en hora de Lima", () => {
  it("muestra la hora de Lima sin importar la zona del equipo", () => {
    // 15:05 UTC = 10:05 en Lima (UTC-5, sin horario de verano)
    expect(fmt.time("2026-09-29T15:05:00Z")).toBe("10:05");
    expect(fmt.dateTime("2026-09-29T15:05:00Z")).toBe("29/09/2026, 10:05");
  });

  it("calcula el día operativo en Lima (a las 23:30 de Lima ya es el día siguiente en UTC)", () => {
    expect(todayIso(new Date("2026-09-30T04:30:00Z"))).toBe("2026-09-29");
  });

  it("formatea fechas de negocio sin corrimiento de día", () => {
    expect(fmt.date("2026-01-01")).toBe("01/01/2026");
    expect(fmt.longDate("2026-09-29")).toBe("Martes, 29 de setiembre"); // es-PE usa «setiembre»
    expect(addDaysIso("2026-02-28", 1)).toBe("2026-03-01");
  });

  it("cuenta regresiva y minutos transcurridos", () => {
    const now = Date.parse("2026-09-29T15:00:00Z");
    expect(countdown("2026-09-29T15:06:05Z", now)).toBe("06:05");
    expect(countdown("2026-09-29T14:59:00Z", now)).toBeNull();
    expect(minutesSince("2026-09-29T14:48:30Z", now)).toBe(11);
  });

  it("muestra guion ante valores vacíos", () => {
    expect(fmt.time(null)).toBe("—");
    expect(fmt.date(undefined)).toBe("—");
  });
});
