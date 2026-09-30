import { CalendarSearch, FilterX } from "lucide-react";
import { useState } from "react";

import type { Appointment } from "@/shared/api/types";
import { useSite } from "@/shared/auth/SiteProvider";
import { addDaysIso, fmt, todayIso } from "@/shared/lib/format";
import { useDebounced, useDocumentTitle } from "@/shared/lib/hooks";
import { CHANNEL_LABEL, STATUS } from "@/shared/lib/status";
import { Button, Card, DataTable, Field, Input, PageHeader, Pagination, Select, StatusBadge, type Column } from "@/shared/ui";

import { useAppointmentSearch } from "./api";
import { AppointmentDrawer } from "./components/AppointmentDrawer";

const PAGE_SIZE = 25;

export default function AppointmentsPage() {
  useDocumentTitle("Atenciones");
  const { sites, site } = useSite();
  const today = todayIso();
  const [siteId, setSiteId] = useState<string>(site ? String(site.id) : "");
  const [dateFrom, setDateFrom] = useState(addDaysIso(today, -6));
  const [dateTo, setDateTo] = useState(today);
  const [status, setStatus] = useState("");
  const [dni, setDni] = useState("");
  const [page, setPage] = useState(1);
  const [detailId, setDetailId] = useState<string | null>(null);
  const debouncedDni = useDebounced(dni, 400);

  const validDni = /^\d{8}$/.test(debouncedDni) ? debouncedDni : undefined;
  const { data, isLoading, isFetching } = useAppointmentSearch({
    site_id: siteId ? Number(siteId) : undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    status: status || undefined,
    document_number: validDni,
    page,
    size: PAGE_SIZE,
  });

  const reset = () => {
    setSiteId(site ? String(site.id) : "");
    setDateFrom(addDaysIso(today, -6));
    setDateTo(today);
    setStatus("");
    setDni("");
    setPage(1);
  };
  const withReset = <T,>(setter: (v: T) => void) => (v: T) => {
    setter(v);
    setPage(1);
  };

  const columns: Column<Appointment>[] = [
    { key: "date", header: "Fecha", cell: (a) => <span className="tabular">{fmt.date(a.service_date)}</span> },
    {
      key: "ticket",
      header: "Turno",
      cell: (a) => <span className="tabular font-semibold whitespace-nowrap">{a.ticket_code}</span>,
    },
    {
      key: "worker",
      header: "Trabajador",
      cell: (a) => (
        <div className="min-w-0">
          <p className="truncate font-medium">{a.worker.display_name}</p>
          <p className="tabular text-xs text-ink-soft">DNI {a.worker.document_number}</p>
        </div>
      ),
    },
    { key: "site", header: "Sede", cell: (a) => a.site_name.replace("Sede ", ""), hideOnMobile: true },
    { key: "channel", header: "Canal", cell: (a) => CHANNEL_LABEL[a.channel] ?? a.channel, hideOnMobile: true },
    { key: "registered", header: "Registro", cell: (a) => <span className="tabular">{fmt.time(a.registered_at)}</span>, hideOnMobile: true },
    { key: "status", header: "Estado", cell: (a) => <StatusBadge status={a.status} size="sm" /> },
  ];

  return (
    <div>
      <PageHeader
        eyebrow="Operación"
        title="Atenciones"
        description="Historial de solicitudes con su estado y trazabilidad completa. Seleccione una fila para ver la línea de tiempo."
      />
      <Card>
        <div className="grid gap-3 border-b border-line p-4 sm:grid-cols-2 lg:grid-cols-[1fr_1fr_1fr_1fr_1fr_auto] lg:items-end">
          <Field label="Sede">
            <Select value={siteId} onChange={(e) => withReset(setSiteId)(e.target.value)}>
              <option value="">Todas mis sedes</option>
              {sites.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.short_name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Desde">
            <Input type="date" value={dateFrom} max={dateTo} onChange={(e) => withReset(setDateFrom)(e.target.value)} />
          </Field>
          <Field label="Hasta">
            <Input type="date" value={dateTo} min={dateFrom} onChange={(e) => withReset(setDateTo)(e.target.value)} />
          </Field>
          <Field label="Estado">
            <Select value={status} onChange={(e) => withReset(setStatus)(e.target.value)}>
              <option value="">Todos</option>
              {Object.entries(STATUS).map(([code, s]) => (
                <option key={code} value={code}>
                  {s.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="DNI">
            <Input
              inputMode="numeric"
              placeholder="8 dígitos"
              value={dni}
              onChange={(e) => withReset(setDni)(e.target.value.replace(/\D/g, "").slice(0, 8))}
              className="tabular"
            />
          </Field>
          <Button variant="ghost" onClick={reset} icon={<FilterX className="size-4" />}>
            Limpiar
          </Button>
        </div>
        <DataTable
          columns={columns}
          rows={data?.items}
          rowKey={(a) => a.public_id}
          loading={isLoading}
          onRowClick={(a) => setDetailId(a.public_id)}
          caption="Atenciones"
          className={isFetching && !isLoading ? "opacity-70 transition-opacity" : undefined}
          empty={{ icon: CalendarSearch, title: "No hay atenciones con estos filtros", description: "Amplíe el rango de fechas o quite filtros." }}
        />
        {data && data.total > 0 && <Pagination page={page} size={PAGE_SIZE} total={data.total} onPageChange={setPage} />}
      </Card>
      <AppointmentDrawer appointmentId={detailId} onClose={() => setDetailId(null)} />
    </div>
  );
}
