import { useState, type ReactNode } from "react";

import { useSite } from "@/shared/auth/SiteProvider";
import { addDaysIso, fmt, todayIso } from "@/shared/lib/format";
import { Field, Input, Segmented, Select } from "@/shared/ui";

const PRESETS = { "7": 7, "30": 30, "90": 90 } as const;
export type Preset = keyof typeof PRESETS | "custom";

/** Sede y periodo de un reporte (presets de 7/30/90 días o rango personalizado). */
export function usePeriod(initial: Preset = "30") {
  const today = todayIso();
  const [siteId, setSiteId] = useState("");
  const [preset, setPreset] = useState<Preset>(initial);
  const [from, setFrom] = useState(addDaysIso(today, -29));
  const [to, setTo] = useState(today);
  const range = preset === "custom" ? { from, to } : { from: addDaysIso(today, -(PRESETS[preset] - 1)), to: today };
  return {
    today,
    siteId,
    setSiteId,
    preset,
    setPreset,
    from,
    setFrom,
    to,
    setTo,
    range,
    params: { date_from: range.from, date_to: range.to, site_id: siteId || undefined },
  };
}

export type Period = Omit<ReturnType<typeof usePeriod>, "setSiteId" | "setPreset" | "setFrom" | "setTo"> & {
  setSiteId: (value: string) => void;
  setPreset: (value: Preset) => void;
  setFrom: (value: string) => void;
  setTo: (value: string) => void;
};

export function PeriodFilter({ period, children }: { period: Period; children?: ReactNode }) {
  const { sites } = useSite();
  const { today, siteId, setSiteId, preset, setPreset, from, setFrom, to, setTo, range } = period;
  return (
    <div className="flex flex-wrap items-end gap-3">
      <Field label="Sede" className="w-56">
        <Select value={siteId} onChange={(e) => setSiteId(e.target.value)}>
          <option value="">Todas mis sedes</option>
          {sites.map((s) => (
            <option key={s.id} value={s.id}>
              {s.short_name}
            </option>
          ))}
        </Select>
      </Field>
      <div className="flex flex-col gap-1.5">
        <span className="text-[0.8125rem] font-medium">Periodo</span>
        <Segmented
          label="Periodo"
          value={preset}
          onChange={setPreset}
          options={[
            { value: "7", label: "7 días" },
            { value: "30", label: "30 días" },
            { value: "90", label: "90 días" },
            { value: "custom", label: "Personalizado" },
          ]}
        />
      </div>
      {preset === "custom" && (
        <>
          <Field label="Desde">
            <Input type="date" value={from} max={to} onChange={(e) => setFrom(e.target.value)} />
          </Field>
          <Field label="Hasta">
            <Input type="date" value={to} min={from} max={today} onChange={(e) => setTo(e.target.value)} />
          </Field>
        </>
      )}
      {children}
      <p className="tabular ml-auto pb-2 text-[0.8125rem] text-ink-soft">
        {fmt.date(range.from)} – {fmt.date(range.to)}
      </p>
    </div>
  );
}
