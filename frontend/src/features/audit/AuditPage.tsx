import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import { FilterX, ShieldAlert, ShieldCheck, ScrollText } from "lucide-react";
import { useState } from "react";

import { api } from "@/shared/api/client";
import type { AuditEvent, ChainVerification, Page } from "@/shared/api/types";
import { useAuth } from "@/shared/auth/AuthProvider";
import { useSite } from "@/shared/auth/SiteProvider";
import { addDaysIso, fmt, todayIso } from "@/shared/lib/format";
import { useDebounced, useDocumentTitle } from "@/shared/lib/hooks";
import { notify } from "@/shared/lib/notify";
import {
  Badge,
  Button,
  Callout,
  Card,
  DataTable,
  DefinitionList,
  Drawer,
  Field,
  Input,
  PageHeader,
  Pagination,
  Select,
  type Column,
} from "@/shared/ui";

const ACTION_LABEL: Record<string, string> = {
  LOGIN: "Inicio de sesión",
  LOGOUT: "Cierre de sesión",
  PASSWORD_CHANGE: "Cambio de contraseña",
  SESSION_REUSE_DETECTED: "Reutilización de sesión detectada",
  ACCESS_DENIED: "Acceso denegado",
  APPOINTMENT_REGISTER: "Registro de atención",
  APPOINTMENT_CALL: "Llamado",
  APPOINTMENT_START: "Inicio de atención",
  APPOINTMENT_FINISH: "Fin de atención",
  APPOINTMENT_REQUEUE: "Devolución a la cola",
  APPOINTMENT_CANCEL: "Cancelación",
  APPOINTMENT_NO_SHOW: "No presentado",
  APPOINTMENT_VOID: "Anulación",
  APPOINTMENT_ACTIVATE: "Activación automática",
  WORKER_VIEW: "Consulta de ficha de trabajador",
  WORKER_CREATE: "Alta de trabajador",
  WORKER_UPDATE: "Modificación de trabajador",
  WORKER_COVERAGE_ADD: "Alta de cobertura EPS",
  WORKER_COVERAGE_END: "Término de cobertura EPS",
  IMPORT_UPLOAD: "Carga de importación",
  IMPORT_CONFIRM: "Confirmación de importación",
  IMPORT_DISCARD: "Descarte de importación",
  SITE_UPDATE: "Modificación de sede",
  SITE_SETTINGS_CHANGE: "Cambio de configuración",
  SITE_SCHEDULE_CHANGE: "Cambio de horario",
  SITE_CLOSURE_ADD: "Registro de cierre",
  SITE_CLOSURE_REMOVE: "Eliminación de cierre",
  SERVICE_DAY_CAPACITY_ADJUST: "Ajuste de capacidad del día",
  USER_CREATE: "Alta de usuario",
  USER_UPDATE: "Modificación de usuario",
  USER_PERMISSIONS_CHANGE: "Cambio de roles/sedes",
  USER_PASSWORD_RESET: "Restablecimiento de contraseña",
  USER_UNLOCK: "Desbloqueo de usuario",
  ROLE_PERMISSIONS_CHANGE: "Cambio de permisos de rol",
  PARAMETER_CHANGE: "Cambio de parámetro",
  REASON_CREATE: "Alta de motivo",
  REASON_UPDATE: "Modificación de motivo",
  TEMPLATE_UPDATE: "Modificación de plantilla",
  NOTIFICATION_RESEND: "Reenvío de notificación",
  REPORT_EXPORT: "Exportación de reporte",
  AUDIT_CHAIN_VERIFY: "Verificación de auditoría",
};
const RESULT_TONE = { SUCCESS: "success", DENIED: "danger", FAILURE: "warning" } as const;
const RESULT_LABEL: Record<string, string> = { SUCCESS: "Éxito", DENIED: "Denegado", FAILURE: "Fallido" };

function JsonBlock({ title, value }: { title: string; value: unknown }) {
  if (value === null || value === undefined) return null;
  return (
    <div>
      <p className="mb-1.5 text-xs font-semibold tracking-wide text-ink-soft uppercase">{title}</p>
      <pre className="overflow-x-auto rounded-xl bg-sunken p-3 font-mono text-xs leading-relaxed text-ink">
        {JSON.stringify(value, null, 2)}
      </pre>
    </div>
  );
}

export default function AuditPage() {
  useDocumentTitle("Auditoría");
  const { can } = useAuth();
  const { sites } = useSite();
  const today = todayIso();
  const [filters, setFilters] = useState({ date_from: addDaysIso(today, -6), date_to: today, username: "", action: "", result: "", site_id: "" });
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<AuditEvent | null>(null);
  const username = useDebounced(filters.username.trim(), 400);
  const params = { ...filters, username, page, size: 50 };

  const { data, isLoading } = useQuery({
    queryKey: ["audit", params],
    queryFn: () => api.get<Page<AuditEvent>>("/audit-events", params),
    placeholderData: keepPreviousData,
  });
  const verify = useMutation({
    mutationFn: () => api.post<ChainVerification>("/audit-events/verify"),
    onError: (e) => notify.error(e),
  });

  const set = (key: keyof typeof filters) => (value: string) => {
    setFilters((f) => ({ ...f, [key]: value }));
    setPage(1);
  };
  const siteName = (id: number | null | undefined) => sites.find((s) => s.id === id)?.short_name ?? (id ? `Sede ${id}` : "—");

  const columns: Column<AuditEvent>[] = [
    { key: "seq", header: "#", cell: (e) => <span className="tabular text-ink-soft">{e.chain_seq}</span>, className: "w-16" },
    { key: "when", header: "Fecha y hora", cell: (e) => <span className="tabular whitespace-nowrap">{fmt.dateTime(e.occurred_at)}</span> },
    { key: "user", header: "Usuario", cell: (e) => e.username ?? "sistema" },
    {
      key: "action",
      header: "Acción",
      cell: (e) => (
        <div>
          <p className="font-medium">{ACTION_LABEL[e.action] ?? e.action}</p>
          {e.reason && <p className="max-w-xs truncate text-xs text-ink-soft">{e.reason}</p>}
        </div>
      ),
    },
    { key: "site", header: "Sede", cell: (e) => siteName(e.site_id), hideOnMobile: true },
    { key: "ip", header: "IP", cell: (e) => <span className="tabular text-ink-soft">{e.ip ?? "—"}</span>, hideOnMobile: true },
    {
      key: "result",
      header: "Resultado",
      cell: (e) => <Badge tone={RESULT_TONE[e.result as keyof typeof RESULT_TONE] ?? "neutral"}>{RESULT_LABEL[e.result] ?? e.result}</Badge>,
    },
  ];

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Control"
        title="Auditoría"
        description="Registro inalterable de las acciones del sistema. Cada evento está encadenado criptográficamente con el anterior."
        actions={
          can("audit:verify") && (
            <Button variant="secondary" loading={verify.isPending} onClick={() => verify.mutate()} icon={<ShieldCheck className="size-4" />}>
              Verificar integridad
            </Button>
          )
        }
      />
      {verify.data &&
        (verify.data.intact ? (
          <Callout tone="success" title="Auditoría íntegra">
            Se verificaron {verify.data.events_checked.toLocaleString("es-PE")} eventos el {fmt.dateTime(verify.data.verified_at)}. No se
            detectaron alteraciones ni eliminaciones.
          </Callout>
        ) : (
          <Callout tone="danger" title="¡Se detectaron alteraciones en la auditoría!">
            {verify.data.problems.length} problema(s): {verify.data.problems.slice(0, 5).map((p) => `evento #${p.chain_seq} (${p.problem})`).join(", ")}.
            Informe de inmediato al área de seguridad de la información.
          </Callout>
        ))}

      <Card>
        <div className="grid gap-3 border-b border-line p-4 sm:grid-cols-3 lg:grid-cols-[repeat(6,minmax(0,1fr))_auto] lg:items-end">
          <Field label="Desde">
            <Input type="date" value={filters.date_from} onChange={(e) => set("date_from")(e.target.value)} />
          </Field>
          <Field label="Hasta">
            <Input type="date" value={filters.date_to} onChange={(e) => set("date_to")(e.target.value)} />
          </Field>
          <Field label="Usuario">
            <Input value={filters.username} onChange={(e) => set("username")(e.target.value)} placeholder="usuario" autoCapitalize="none" />
          </Field>
          <Field label="Acción">
            <Select value={filters.action} onChange={(e) => set("action")(e.target.value)}>
              <option value="">Todas</option>
              {Object.entries(ACTION_LABEL)
                .sort((a, b) => a[1].localeCompare(b[1]))
                .map(([code, label]) => (
                  <option key={code} value={code}>
                    {label}
                  </option>
                ))}
            </Select>
          </Field>
          <Field label="Resultado">
            <Select value={filters.result} onChange={(e) => set("result")(e.target.value)}>
              <option value="">Todos</option>
              <option value="SUCCESS">Éxito</option>
              <option value="DENIED">Denegado</option>
              <option value="FAILURE">Fallido</option>
            </Select>
          </Field>
          <Field label="Sede">
            <Select value={filters.site_id} onChange={(e) => set("site_id")(e.target.value)}>
              <option value="">Todas</option>
              {sites.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.short_name}
                </option>
              ))}
            </Select>
          </Field>
          <Button
            variant="ghost"
            icon={<FilterX className="size-4" />}
            onClick={() => {
              setFilters({ date_from: addDaysIso(today, -6), date_to: today, username: "", action: "", result: "", site_id: "" });
              setPage(1);
            }}
          >
            Limpiar
          </Button>
        </div>
        <DataTable
          columns={columns}
          rows={data?.items}
          rowKey={(e) => e.chain_seq}
          loading={isLoading}
          onRowClick={setSelected}
          caption="Eventos de auditoría"
          empty={{ icon: ScrollText, title: "Sin eventos con estos filtros" }}
        />
        {data && data.total > 0 && <Pagination page={page} size={50} total={data.total} onPageChange={setPage} />}
      </Card>

      <Drawer
        open={Boolean(selected)}
        onOpenChange={(o) => !o && setSelected(null)}
        title={selected ? (ACTION_LABEL[selected.action] ?? selected.action) : ""}
        description={selected ? `Evento #${selected.chain_seq} · ${fmt.dateTime(selected.occurred_at)}` : undefined}
      >
        {selected && (
          <div className="space-y-6">
            {selected.result === "DENIED" && (
              <Callout tone="danger" title="Acceso denegado">
                <ShieldAlert className="mr-1 inline size-4" /> {selected.reason}
              </Callout>
            )}
            <DefinitionList
              items={[
                ["Usuario", selected.username ?? "sistema"],
                ["Resultado", RESULT_LABEL[selected.result] ?? selected.result],
                ["Recurso", selected.resource_type ? `${selected.resource_type} · ${selected.resource_id ?? ""}` : "—"],
                ["Sede", siteName(selected.site_id)],
                ["IP", selected.ip ?? "—"],
                ["Solicitud", <span className="font-mono text-xs">{selected.request_id ?? "—"}</span>],
                ["Motivo", selected.reason ?? "—"],
              ]}
            />
            <JsonBlock title="Valores anteriores" value={selected.before_data} />
            <JsonBlock title="Valores nuevos" value={selected.after_data} />
            <JsonBlock title="Metadatos" value={selected.metadata} />
          </div>
        )}
      </Drawer>
    </div>
  );
}
