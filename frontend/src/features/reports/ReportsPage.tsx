import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { BarChart3, CalendarCheck2, Clock3, Download, FileSpreadsheet, FileText, Gauge, MessageSquareQuote, Star, Stethoscope, Timer, UserX } from "lucide-react";
import { useMemo, useState } from "react";

import { api } from "@/shared/api/client";
import type { components } from "@/shared/api/schema";
import { useAuth } from "@/shared/auth/AuthProvider";
import { useSite } from "@/shared/auth/SiteProvider";
import { BarList } from "@/shared/charts/BarList";
import { ColumnChart, type ChartSeries } from "@/shared/charts/ColumnChart";
import { addDaysIso, fmt, todayIso } from "@/shared/lib/format";
import { useDocumentTitle } from "@/shared/lib/hooks";
import { notify } from "@/shared/lib/notify";
import { CHANNEL_LABEL } from "@/shared/lib/status";
import {
  Button,
  Card,
  CardHeader,
  DataTable,
  EmptyState,
  Field,
  Input,
  KpiCard,
  Menu,
  MenuContent,
  MenuItem,
  MenuLabel,
  MenuSeparator,
  MenuTrigger,
  PageHeader,
  Segmented,
  Select,
  Skeleton,
  type Column,
} from "@/shared/ui";

type Summary = components["schemas"]["ReportSummaryOut"];
type Day = components["schemas"]["ReportDayOut"];

// Paleta categórica validada (CVD, todas las parejas): azul, naranja, aqua.
// El aqua tiene contraste < 3:1 → alivio obligatorio: la tabla con los mismos datos está en la página.
const OUTCOME_SERIES: ChartSeries[] = [
  { key: "attended", label: "Atendidos", color: "#2a78d6" },
  { key: "no_show", label: "No presentados", color: "#eb6834" },
  { key: "cancelled", label: "Cancelados", color: "#1baf7a" },
];
const SINGLE_SERIES_COLOR = "#93263a"; // granate institucional (validado para marcas de datos)

const PRESETS = { "7": 7, "30": 30, "90": 90 } as const;

export default function ReportsPage() {
  useDocumentTitle("Reportes");
  const { can } = useAuth();
  const { sites } = useSite();
  const today = todayIso();
  const [siteId, setSiteId] = useState("");
  const [preset, setPreset] = useState<"7" | "30" | "90" | "custom">("30");
  const [from, setFrom] = useState(addDaysIso(today, -29));
  const [to, setTo] = useState(today);

  const range = preset === "custom" ? { from, to } : { from: addDaysIso(today, -(PRESETS[preset] - 1)), to: today };
  const params = { date_from: range.from, date_to: range.to, site_id: siteId || undefined };
  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["reports", params],
    queryFn: () => api.get<Summary>("/reports/summary", params),
    placeholderData: keepPreviousData,
  });

  // Serie diaria agregada (todas las sedes seleccionadas), incluyendo días sin atenciones.
  const daily = useMemo(() => {
    if (!data) return [];
    const byDate = new Map<string, { attended: number; no_show: number; cancelled: number; capacity: number; requested: number }>();
    for (const d of data.by_day) {
      const row = byDate.get(d.service_date) ?? { attended: 0, no_show: 0, cancelled: 0, capacity: 0, requested: 0 };
      row.attended += d.attended;
      row.no_show += d.no_show;
      row.cancelled += d.cancelled;
      row.capacity += d.capacity;
      row.requested += d.requested;
      byDate.set(d.service_date, row);
    }
    return [...byDate.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, v]) => ({
        label: fmt.date(date).slice(0, 5),
        title: fmt.longDate(date),
        values: { attended: v.attended, no_show: v.no_show, cancelled: v.cancelled },
        reference: v.capacity,
      }));
  }, [data]);

  const hourly = useMemo(() => {
    if (!data) return [];
    const counts = new Map(data.by_hour.map((h) => [h.hour, h.count]));
    const hours = data.by_hour.length ? data.by_hour.map((h) => h.hour) : [8, 17];
    const [minH, maxH] = [Math.min(7, ...hours), Math.max(17, ...hours)];
    return Array.from({ length: maxH - minH + 1 }, (_, i) => minH + i).map((h) => ({
      label: `${String(h).padStart(2, "0")}h`,
      title: `${String(h).padStart(2, "0")}:00 – ${String(h).padStart(2, "0")}:59`,
      values: { count: counts.get(h) ?? 0 },
    }));
  }, [data]);

  const exportReport = (report: "summary" | "daily" | "appointments", format: "xlsx" | "pdf" | "csv") =>
    void api
      .download("/reports/export", { report, format, ...params })
      .then(() => notify.success("Exportación generada", "La descarga quedó registrada en la auditoría."))
      .catch((e) => notify.error(e));

  const totals = data?.totals;
  const dayColumns: Column<Day>[] = [
    { key: "date", header: "Fecha", cell: (d) => <span className="tabular">{fmt.date(d.service_date)}</span> },
    { key: "site", header: "Sede", cell: (d) => d.site_name },
    { key: "cap", header: "Capacidad", cell: (d) => <span className="tabular">{d.capacity}</span>, className: "text-right", headerClassName: "text-right" },
    { key: "req", header: "Solicitudes", cell: (d) => <span className="tabular">{d.requested}</span>, className: "text-right", headerClassName: "text-right" },
    { key: "att", header: "Atendidos", cell: (d) => <span className="tabular">{d.attended}</span>, className: "text-right", headerClassName: "text-right" },
    { key: "ns", header: "No pres.", cell: (d) => <span className="tabular">{d.no_show}</span>, className: "text-right", headerClassName: "text-right" },
    { key: "can", header: "Cancel.", cell: (d) => <span className="tabular">{d.cancelled}</span>, className: "text-right", headerClassName: "text-right" },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Gestión"
        title="Reportes"
        description="Indicadores agregados del servicio. No incluyen datos personales; el listado nominal requiere un permiso específico."
        actions={
          <Menu>
            <MenuTrigger asChild>
              <Button variant="secondary" icon={<Download className="size-4" />}>
                Exportar
              </Button>
            </MenuTrigger>
            <MenuContent>
              <MenuLabel>Reporte de indicadores (periodo y sede seleccionados)</MenuLabel>
              <MenuItem onSelect={() => exportReport("summary", "pdf")}>
                <FileText className="size-4" /> PDF
              </MenuItem>
              <MenuItem onSelect={() => exportReport("summary", "xlsx")}>
                <FileSpreadsheet className="size-4" /> Excel (.xlsx)
              </MenuItem>
              <MenuItem onSelect={() => exportReport("daily", "csv")}>Detalle por día (CSV)</MenuItem>
              {can("report:export") && can("report:read_nominal") && (
                <>
                  <MenuSeparator />
                  <MenuLabel>Listado nominal (datos personales)</MenuLabel>
                  <MenuItem onSelect={() => exportReport("appointments", "pdf")}>
                    <FileText className="size-4" /> PDF
                  </MenuItem>
                  <MenuItem onSelect={() => exportReport("appointments", "xlsx")}>
                    <FileSpreadsheet className="size-4" /> Excel (.xlsx)
                  </MenuItem>
                  <MenuItem onSelect={() => exportReport("appointments", "csv")}>CSV</MenuItem>
                </>
              )}
            </MenuContent>
          </Menu>
        }
      />

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
          <span className="text-[13px] font-medium">Periodo</span>
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
        <p className="tabular ml-auto pb-2 text-[13px] text-ink-soft">
          {fmt.date(range.from)} – {fmt.date(range.to)}
        </p>
      </div>

      {isLoading || !totals ? (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-6">
          {Array.from({ length: 6 }, (_, i) => (
            <Skeleton key={i} className="h-[74px] rounded-[var(--radius-card)]" />
          ))}
        </div>
      ) : (
        <div className={`grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6 ${isFetching ? "opacity-70" : ""}`}>
          <KpiCard label="Solicitudes" value={fmt.number(totals.requested)} icon={CalendarCheck2} tone="brand" hint={`${totals.voided} anuladas no se cuentan`} emphasis />
          <KpiCard label="Atendidos" value={fmt.number(totals.attended)} icon={BarChart3} tone="done" hint={`${totals.pending} aún en curso`} />
          <KpiCard
            label="Uso de cupos"
            value={totals.utilization_pct !== null ? `${fmt.number(totals.utilization_pct, 1)}%` : "—"}
            icon={Gauge}
            hint={`${fmt.number(totals.attended)} de ${fmt.number(totals.capacity)} cupos`}
          />
          <KpiCard
            label="Inasistencia"
            value={totals.no_show_pct !== null ? `${fmt.number(totals.no_show_pct, 1)}%` : "—"}
            icon={UserX}
            tone={totals.no_show > 0 ? "danger" : "neutral"}
            hint={`${totals.no_show} casos · ${totals.cancelled} cancelaciones`}
          />
          <KpiCard
            label="Espera prom."
            value={totals.avg_wait_minutes !== null ? `${fmt.number(totals.avg_wait_minutes)} min` : "—"}
            icon={Clock3}
            hint="del registro al inicio"
          />
          <KpiCard
            label="Duración prom."
            value={totals.avg_service_minutes !== null ? `${fmt.number(totals.avg_service_minutes)} min` : "—"}
            icon={Timer}
            hint="por atención"
          />
        </div>
      )}

      {data && data.totals.requested === 0 ? (
        <Card>
          <EmptyState icon={BarChart3} title="Sin atenciones en el periodo" description="Seleccione otro periodo o sede." />
        </Card>
      ) : (
        <>
          <Card>
            <CardHeader title="Resultado diario vs. capacidad" description="Columnas apiladas por resultado; la línea marca la capacidad del día." />
            <div className="p-5">
              {data ? (
                <ColumnChart data={daily} series={OUTCOME_SERIES} referenceLabel="Capacidad" ariaLabel="Atenciones por día según resultado" height={260} />
              ) : (
                <Skeleton className="h-64" />
              )}
            </div>
          </Card>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader title="Demanda por hora de registro" description="Solicitudes según la hora en que fueron registradas." />
              <div className="p-5">
                {data && (
                  <ColumnChart
                    data={hourly}
                    series={[{ key: "count", label: "Solicitudes", color: SINGLE_SERIES_COLOR }]}
                    ariaLabel="Solicitudes por hora de registro"
                    height={220}
                  />
                )}
              </div>
            </Card>
            <Card>
              <CardHeader title="Dependencias con más solicitudes" description="Top 10 del periodo." />
              <div className="p-5">
                {data && (
                  <BarList
                    ariaLabel="Solicitudes por dependencia"
                    color={SINGLE_SERIES_COLOR}
                    items={data.by_department.slice(0, 10).map((d) => ({ label: d.department, value: d.count }))}
                  />
                )}
                {data && data.by_channel.length > 0 && (
                  <p className="mt-5 border-t border-line pt-4 text-[13px] text-ink-muted">
                    Canal:{" "}
                    {data.by_channel.map((c, i) => (
                      <span key={c.channel}>
                        {i > 0 && " · "}
                        {CHANNEL_LABEL[c.channel] ?? c.channel} <span className="tabular font-semibold text-ink">{c.count}</span>
                      </span>
                    ))}
                  </p>
                )}
              </div>
            </Card>
          </div>

          {data && data.by_doctor.length > 0 && (
            <Card>
              <CardHeader
                title="Atenciones por médico"
                description="Atenciones finalizadas en el periodo y duración promedio."
                icon={<Stethoscope className="size-[18px]" />}
              />
              <div className="p-5">
                <BarList
                  ariaLabel="Atenciones por médico"
                  color={SINGLE_SERIES_COLOR}
                  items={data.by_doctor.map((d) => ({
                    label: d.avg_service_minutes !== null ? `${d.doctor} · ${fmt.number(d.avg_service_minutes)} min prom.` : d.doctor,
                    value: d.attended,
                  }))}
                />
              </div>
            </Card>
          )}

          {data && data.rating.invited > 0 && (
            <Card>
              <CardHeader
                title="Satisfacción del servicio"
                description={`Calificación anónima: ${data.rating.count} respuesta(s) de ${data.rating.invited} invitación(es) enviadas al finalizar la atención.`}
                icon={<Star className="size-[18px]" />}
              />
              <div className="grid gap-6 p-5 lg:grid-cols-[220px_1fr_1.2fr]">
                <div className="space-y-3">
                  <div>
                    <p className="text-xs font-medium tracking-wide text-ink-soft uppercase">Trato</p>
                    <p className="tabular text-3xl font-semibold">
                      {data.rating.avg_score !== null ? fmt.number(data.rating.avg_score, 1) : "—"}
                      <span className="text-base font-normal text-ink-soft"> / 5</span>
                    </p>
                  </div>
                  <div>
                    <p className="text-xs font-medium tracking-wide text-ink-soft uppercase">Tiempo de espera</p>
                    <p className="tabular text-2xl font-semibold">
                      {data.rating.avg_wait_score !== null ? fmt.number(data.rating.avg_wait_score, 1) : "—"}
                      <span className="text-base font-normal text-ink-soft"> / 5</span>
                    </p>
                  </div>
                </div>
                <BarList
                  ariaLabel="Distribución de calificaciones"
                  color={SINGLE_SERIES_COLOR}
                  items={[...data.rating.distribution].reverse().map((b) => ({ label: `${b.score} estrella${b.score > 1 ? "s" : ""}`, value: b.count }))}
                />
                <div>
                  <p className="mb-2 flex items-center gap-1.5 text-[13px] font-medium text-ink-muted">
                    <MessageSquareQuote className="size-4" aria-hidden /> Comentarios recientes
                  </p>
                  {data.rating.comments.length === 0 ? (
                    <p className="text-sm text-ink-soft">Sin comentarios en el periodo.</p>
                  ) : (
                    <ul className="max-h-56 space-y-2 overflow-y-auto pr-1">
                      {data.rating.comments.map((c, i) => (
                        <li key={i} className="rounded-lg bg-sunken/60 px-3 py-2 text-sm">
                          <p className="text-ink">«{c.comment}»</p>
                          <p className="mt-0.5 text-xs text-ink-soft">
                            {"★".repeat(c.score)} · {c.site_name} · {fmt.date(c.service_date)}
                          </p>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            </Card>
          )}

          <Card>
            <CardHeader title="Detalle por día y sede" description="Los mismos datos del gráfico, en tabla." />
            <DataTable
              columns={dayColumns}
              rows={data ? [...data.by_day].reverse() : undefined}
              rowKey={(d) => `${d.service_date}-${d.site_id}`}
              loading={isLoading}
              caption="Detalle diario"
            />
          </Card>
        </>
      )}
    </div>
  );
}
