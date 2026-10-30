import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Download, FileSpreadsheet, FileText, MessageSquareQuote, Send, Star, Timer } from "lucide-react";
import { useState } from "react";

import { useDoctors } from "@/features/appointments/api";
import { api } from "@/shared/api/client";
import type { components } from "@/shared/api/schema";
import { BarList } from "@/shared/charts/BarList";
import { ColumnChart } from "@/shared/charts/ColumnChart";
import { fmt } from "@/shared/lib/format";
import { useDocumentTitle } from "@/shared/lib/hooks";
import { notify } from "@/shared/lib/notify";
import {
  Button,
  Card,
  CardHeader,
  DataTable,
  EmptyState,
  Field,
  KpiCard,
  Menu,
  MenuContent,
  MenuItem,
  MenuLabel,
  MenuTrigger,
  PageHeader,
  Pagination,
  Select,
  Skeleton,
  type Column,
} from "@/shared/ui";

import { PeriodFilter, usePeriod, type Period, type Preset } from "./PeriodFilter";

type S = components["schemas"];
type Report = S["SatisfactionReportOut"];
type Group = Pick<S["SatisfactionSiteOut"], "count" | "avg_score" | "avg_wait_score">;
type Comment = S["SatisfactionCommentOut"];

const PAGE_SIZE = 20;
const BRAND_SERIES = "#93263a"; // granate institucional (validado para marcas de datos)
const MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "set", "oct", "nov", "dic"];

const monthLabel = (value: string) => {
  const [year, month] = value.split("-");
  return `${MONTHS[Number(month) - 1]} ${year}`;
};
const score = (value: number | null | undefined) => (value === null || value === undefined ? "—" : fmt.number(value, 1));
const starsLabel = (n: number) => `${n} estrella${n > 1 ? "s" : ""}`;

function Stars({ value, label }: { value: number; label: string }) {
  return (
    <span className="whitespace-nowrap text-amber-600" role="img" aria-label={`${label}: ${value} de 5`} title={`${label}: ${value} de 5`}>
      {"★".repeat(value)}
      <span className="text-line-strong">{"★".repeat(5 - value)}</span>
    </span>
  );
}

function groupColumns<T extends Group>(header: string, label: (row: T) => string): Column<T>[] {
  const numeric = { className: "text-right", headerClassName: "text-right" };
  return [
    { key: "label", header, cell: (r) => label(r) },
    { key: "count", header: "Respuestas", cell: (r) => <span className="tabular">{r.count}</span>, ...numeric },
    { key: "score", header: "Trato", cell: (r) => <span className="tabular">{score(r.avg_score)}</span>, ...numeric },
    { key: "wait", header: "Espera", cell: (r) => <span className="tabular">{score(r.avg_wait_score)}</span>, ...numeric },
  ];
}

const commentColumns: Column<Comment>[] = [
  { key: "date", header: "Fecha", cell: (c) => <span className="tabular">{fmt.date(c.service_date)}</span> },
  { key: "comment", header: "Comentario", cell: (c) => <span className="text-ink">«{c.comment}»</span>, className: "min-w-[18rem] whitespace-normal" },
  { key: "score", header: "Trato", cell: (c) => <Stars value={c.score} label="Trato" /> },
  { key: "wait", header: "Espera", cell: (c) => (c.wait_score ? <Stars value={c.wait_score} label="Tiempo de espera" /> : "—") },
  { key: "site", header: "Sede", cell: (c) => c.site_name },
  { key: "doctor", header: "Médico", cell: (c) => c.doctor ?? "—" },
];

export default function SatisfactionPage() {
  useDocumentTitle("Satisfacción del servicio");
  const period = usePeriod();
  const [doctorId, setDoctorId] = useState("");
  const [stars, setStars] = useState("");
  const [page, setPage] = useState(1);
  const siteNumber = period.siteId ? Number(period.siteId) : undefined;
  const doctors = useDoctors(siteNumber);

  const filters = { ...period.params, doctor_id: siteNumber && doctorId ? doctorId : undefined, score: stars || undefined };
  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["satisfaction", filters, page],
    queryFn: () => api.get<Report>("/reports/satisfaction", { ...filters, page, page_size: PAGE_SIZE }),
    placeholderData: keepPreviousData,
  });

  // Al cambiar la sede se limpia el médico, y cualquier filtro vuelve a la primera página.
  const filterPeriod: Period = {
    ...period,
    setSiteId: (value: string) => {
      period.setSiteId(value);
      setDoctorId("");
      setPage(1);
    },
    setPreset: (value: Preset) => {
      period.setPreset(value);
      setPage(1);
    },
    setFrom: (value: string) => {
      period.setFrom(value);
      setPage(1);
    },
    setTo: (value: string) => {
      period.setTo(value);
      setPage(1);
    },
  };

  const exportReport = (format: "xlsx" | "pdf") =>
    void api
      .download("/reports/satisfaction/export", { format, ...filters })
      .then(() => notify.success("Exportación generada", "Incluye todos los comentarios. La descarga quedó registrada en la auditoría."))
      .catch((e) => notify.error(e));

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Gestión"
        title="Satisfacción del servicio"
        description="Opinión anónima de los trabajadores al finalizar su atención: no se registra su DNI ni su nombre."
        actions={
          <Menu>
            <MenuTrigger asChild>
              <Button variant="secondary" icon={<Download className="size-4" />}>
                Exportar
              </Button>
            </MenuTrigger>
            <MenuContent>
              <MenuLabel>Reporte con todos los comentarios (filtros actuales)</MenuLabel>
              <MenuItem onSelect={() => exportReport("pdf")}>
                <FileText className="size-4" /> PDF
              </MenuItem>
              <MenuItem onSelect={() => exportReport("xlsx")}>
                <FileSpreadsheet className="size-4" /> Excel (.xlsx)
              </MenuItem>
            </MenuContent>
          </Menu>
        }
      />

      <PeriodFilter period={filterPeriod}>
        <Field label="Médico" className="w-56" hint={siteNumber ? undefined : "Elija primero una sede"}>
          <Select
            value={doctorId}
            disabled={!siteNumber}
            onChange={(e) => {
              setDoctorId(e.target.value);
              setPage(1);
            }}
          >
            <option value="">Todos</option>
            {(doctors.data ?? []).map((d) => (
              <option key={d.id} value={d.id}>
                {d.full_name}
              </option>
            ))}
          </Select>
        </Field>
      </PeriodFilter>

      {isLoading || !data ? (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} className="h-[74px] rounded-[var(--radius-card)]" />
          ))}
        </div>
      ) : (
        <div className={`grid grid-cols-2 gap-3 lg:grid-cols-4 ${isFetching ? "opacity-70" : ""}`}>
          <KpiCard label="Trato" value={`${score(data.avg_score)} / 5`} icon={Star} tone="brand" hint="promedio de 1 a 5" emphasis />
          <KpiCard label="Tiempo de espera" value={`${score(data.avg_wait_score)} / 5`} icon={Timer} hint="promedio de 1 a 5" />
          <KpiCard
            label="Respuestas"
            value={fmt.number(data.count)}
            icon={Send}
            hint={data.response_pct !== null ? `${fmt.number(data.response_pct, 1)}% de ${fmt.number(data.invited)} invitaciones` : "sin invitaciones"}
          />
          <KpiCard label="Con comentario" value={fmt.number(data.with_comment)} icon={MessageSquareQuote} hint="respuestas con texto" />
        </div>
      )}

      {data && data.count === 0 ? (
        <Card>
          <EmptyState icon={Star} title="Sin calificaciones en el periodo" description="Seleccione otro periodo, sede o médico." />
        </Card>
      ) : (
        <>
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader title="Evolución mensual del trato" description="Promedio de 1 a 5 por mes. La tabla incluye el tiempo de espera." />
              <div className="p-5">
                {data ? (
                  <ColumnChart
                    data={data.by_month.map((m) => ({
                      label: monthLabel(m.month),
                      title: `${monthLabel(m.month)} · ${m.count} respuesta(s)`,
                      values: { avg: m.avg_score ?? 0 },
                    }))}
                    series={[{ key: "avg", label: "Trato (1-5)", color: BRAND_SERIES }]}
                    ariaLabel="Promedio de trato por mes"
                    height={200}
                  />
                ) : (
                  <Skeleton className="h-48" />
                )}
              </div>
              <DataTable
                columns={groupColumns<S["SatisfactionMonthOut"]>("Mes", (m) => monthLabel(m.month))}
                rows={data ? [...data.by_month].reverse() : undefined}
                rowKey={(m) => m.month}
                loading={isLoading}
                caption="Satisfacción por mes"
              />
            </Card>
            <Card>
              <CardHeader title="Distribución de calificaciones" description="Cantidad de respuestas según las estrellas." />
              <div className="grid gap-6 p-5 sm:grid-cols-2">
                {data &&
                  (
                    [
                      ["Trato", data.distribution],
                      ["Tiempo de espera", data.wait_distribution],
                    ] as const
                  ).map(([title, buckets]) => (
                    <div key={title}>
                      <p className="mb-2 text-xs font-medium tracking-wide text-ink-soft uppercase">{title}</p>
                      <BarList
                        ariaLabel={`Distribución: ${title}`}
                        color={BRAND_SERIES}
                        items={[...buckets].reverse().map((b) => ({ label: starsLabel(b.score), value: b.count }))}
                      />
                    </div>
                  ))}
              </div>
            </Card>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader title="Por sede" />
              <DataTable
                columns={groupColumns<S["SatisfactionSiteOut"]>("Sede", (r) => r.site_name)}
                rows={data?.by_site}
                rowKey={(r) => r.site_name}
                loading={isLoading}
                caption="Satisfacción por sede"
              />
            </Card>
            <Card>
              <CardHeader title="Por médico" />
              <DataTable
                columns={groupColumns<S["SatisfactionDoctorOut"]>("Médico", (r) => r.doctor)}
                rows={data?.by_doctor}
                rowKey={(r) => r.doctor}
                loading={isLoading}
                caption="Satisfacción por médico"
              />
            </Card>
          </div>

          <Card>
            <CardHeader
              title="Comentarios"
              description={data ? `${fmt.number(data.comments_total)} comentario(s), del más reciente al más antiguo.` : undefined}
              icon={<MessageSquareQuote className="size-[18px]" />}
              actions={
                <Select
                  aria-label="Filtrar comentarios por nota de trato"
                  className="w-44"
                  value={stars}
                  onChange={(e) => {
                    setStars(e.target.value);
                    setPage(1);
                  }}
                >
                  <option value="">Todas las notas</option>
                  {[5, 4, 3, 2, 1].map((n) => (
                    <option key={n} value={n}>
                      {starsLabel(n)}
                    </option>
                  ))}
                </Select>
              }
            />
            <DataTable
              columns={commentColumns}
              rows={data?.comments}
              rowKey={(c) => `${c.submitted_at}-${c.comment}`}
              loading={isLoading}
              caption="Comentarios de los trabajadores"
              empty={{ icon: MessageSquareQuote, title: "Sin comentarios", description: "No hay comentarios con los filtros elegidos." }}
            />
            {data && data.comments_total > PAGE_SIZE && (
              <Pagination page={page} size={PAGE_SIZE} total={data.comments_total} onPageChange={setPage} />
            )}
          </Card>
        </>
      )}
    </div>
  );
}
