import { describe, expect, it } from "vitest";

import { scheduleSummary } from "./DoctorAvailability";

const block = (weekday: number, start: string, end: string) => ({ weekday, start_time: `${start}:00`, end_time: `${end}:00` });

describe("scheduleSummary", () => {
  it("sin horario: todo el horario de la sede", () => {
    expect(scheduleSummary([])).toBe("Todo el horario de la sede");
  });

  it("agrupa días consecutivos con el mismo horario", () => {
    const blocks = [1, 2, 3].map((d) => block(d, "08", "12")).concat([block(5, "08", "12"), block(4, "14", "17")]);
    expect(scheduleSummary(blocks)).toBe("lun–mié, vie 08:00–12:00 · jue 14:00–17:00");
  });
});
