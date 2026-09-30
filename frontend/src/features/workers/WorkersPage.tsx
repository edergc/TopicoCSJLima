import { Mail, MailX, Pencil, Plus, ShieldCheck, ShieldOff, UserRoundX, Users } from "lucide-react";
import { useState } from "react";

import type { WorkerSummary } from "@/shared/api/types";
import { useAuth } from "@/shared/auth/AuthProvider";
import { fmt, todayIso } from "@/shared/lib/format";
import { useDebounced, useDocumentTitle } from "@/shared/lib/hooks";
import { errorMessage, notify } from "@/shared/lib/notify";
import {
  Badge,
  Button,
  Callout,
  Card,
  ConfirmDialog,
  DataTable,
  DefinitionList,
  Drawer,
  Field,
  Input,
  PageHeader,
  Pagination,
  SearchInput,
  Segmented,
  Skeleton,
  Textarea,
  type Column,
} from "@/shared/ui";

import { useAddCoverage, useEndCoverage, useUpdateWorker, useWorker, useWorkerSearch } from "./api";
import { WorkerFormModal } from "./WorkerForm";

const PAGE_SIZE = 25;

function WorkerDetail({ id, onClose }: { id: string | null; onClose: () => void }) {
  const { can } = useAuth();
  const { data: worker, isLoading } = useWorker(id);
  const [editing, setEditing] = useState(false);
  const [deactivating, setDeactivating] = useState(false);
  const [reason, setReason] = useState("");
  const [ending, setEnding] = useState<number | null>(null);
  const [endReason, setEndReason] = useState("");
  const [endDate, setEndDate] = useState(todayIso());
  const update = useUpdateWorker(id ?? "");
  const addCoverage = useAddCoverage(id ?? "");
  const endCoverage = useEndCoverage(id ?? "");
  const canManage = can("worker:manage");
  const today = todayIso();
  const active = worker?.coverages.find((c) => c.valid_from <= today && (!c.valid_to || c.valid_to >= today));

  return (
    <Drawer
      open={Boolean(id)}
      onOpenChange={(o) => !o && onClose()}
      title={worker ? `${worker.paternal_surname} ${worker.maternal_surname ?? ""}, ${worker.first_names}` : "Trabajador"}
      description="Ficha administrativa. Su consulta queda registrada en la auditoría."
      footer={
        canManage && worker ? (
          <>
            {worker.is_active ? (
              <Button variant="ghost" className="mr-auto text-danger" onClick={() => setDeactivating(true)} icon={<UserRoundX className="size-4" />}>
                Desactivar
              </Button>
            ) : (
              <Button
                variant="ghost"
                className="mr-auto"
                loading={update.isPending}
                onClick={() => update.mutate({ is_active: true }, { onSuccess: () => notify.success("Trabajador reactivado") })}
              >
                Reactivar
              </Button>
            )}
            <Button variant="secondary" onClick={() => setEditing(true)} icon={<Pencil className="size-4" />}>
              Editar
            </Button>
          </>
        ) : undefined
      }
    >
      {isLoading || !worker ? (
        <Skeleton className="h-64" />
      ) : (
        <div className="space-y-7">
          <div className="flex flex-wrap gap-2">
            {worker.is_active ? <Badge tone="success">Activo</Badge> : <Badge tone="danger">Inactivo</Badge>}
            {active ? (
              <Badge tone="success">
                <ShieldCheck className="size-3" /> EPS Rímac vigente
              </Badge>
            ) : (
              <Badge tone="warning">
                <ShieldOff className="size-3" /> Sin cobertura vigente
              </Badge>
            )}
          </div>
          <DefinitionList
            items={[
              ["DNI", <span className="tabular">{worker.document_number}</span>],
              ["Código", worker.employee_code ?? "—"],
              ["Dependencia", worker.department_name ?? "—"],
              ["Sexo", worker.sex === "F" ? "Femenino" : worker.sex === "M" ? "Masculino" : "—"],
              ["Edad", worker.age !== null && worker.age !== undefined ? `${worker.age} años` : "—"],
              ["Correo", worker.institutional_email ?? <span className="text-ink-soft">Sin correo</span>],
              ["Teléfono", worker.phone ?? "—"],
              ["Actualizado", fmt.dateTime(worker.updated_at)],
            ]}
          />
          {!worker.is_active && worker.deactivation_reason && (
            <Callout tone="warning" title="Motivo de desactivación">
              {worker.deactivation_reason}
            </Callout>
          )}
          <section>
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-xs font-semibold tracking-wide text-ink-soft uppercase">Cobertura EPS</h3>
              {canManage && !active && (
                <Button
                  size="sm"
                  variant="subtle"
                  loading={addCoverage.isPending}
                  onClick={() =>
                    addCoverage.mutate(
                      { valid_from: today },
                      { onSuccess: () => notify.success("Cobertura registrada"), onError: (e) => notify.error(e) },
                    )
                  }
                  icon={<Plus className="size-3.5" />}
                >
                  Habilitar desde hoy
                </Button>
              )}
            </div>
            {worker.coverages.length === 0 ? (
              <p className="text-sm text-ink-soft">Sin coberturas registradas.</p>
            ) : (
              <ul className="space-y-2">
                {worker.coverages.map((c) => (
                  <li key={c.id} className="flex items-center gap-3 rounded-xl border border-line px-3 py-2.5 text-sm">
                    <div className="flex-1">
                      <p className="font-medium">{c.insurer_name}</p>
                      <p className="tabular text-xs text-ink-soft">
                        {fmt.date(c.valid_from)} — {c.valid_to ? fmt.date(c.valid_to) : "vigente"}
                        {c.end_reason && ` · ${c.end_reason}`}
                      </p>
                    </div>
                    {canManage && !c.valid_to && (
                      <Button size="sm" variant="ghost" onClick={() => setEnding(c.id)}>
                        Terminar
                      </Button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
      {worker && editing && <WorkerFormModal worker={worker} open onClose={() => setEditing(false)} />}
      <ConfirmDialog
        open={deactivating}
        onOpenChange={setDeactivating}
        tone="danger"
        title="Desactivar trabajador"
        description="No podrá registrar atenciones mientras esté inactivo. El historial se conserva."
        confirmLabel="Desactivar"
        loading={update.isPending}
        confirmDisabled={reason.trim().length < 3}
        onConfirm={() =>
          update.mutate(
            { is_active: false, deactivation_reason: reason.trim() },
            {
              onSuccess: () => {
                setDeactivating(false);
                notify.success("Trabajador desactivado");
              },
              onError: (e) => notify.error(e),
            },
          )
        }
      >
        <Field label="Motivo" required>
          <Textarea value={reason} onChange={(e) => setReason(e.target.value)} maxLength={200} rows={2} />
        </Field>
      </ConfirmDialog>
      <ConfirmDialog
        open={ending !== null}
        onOpenChange={(o) => !o && setEnding(null)}
        tone="danger"
        title="Terminar cobertura EPS"
        confirmLabel="Terminar cobertura"
        loading={endCoverage.isPending}
        confirmDisabled={endReason.trim().length < 3 || !endDate}
        onConfirm={() =>
          ending !== null &&
          endCoverage.mutate(
            { coverageId: ending, valid_to: endDate, end_reason: endReason.trim() },
            {
              onSuccess: () => {
                setEnding(null);
                notify.success("Cobertura terminada");
              },
              onError: (e) => notify.error(e),
            },
          )
        }
      >
        <div className="space-y-4">
          <Field label="Vigente hasta" required>
            <Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
          </Field>
          <Field label="Motivo" required>
            <Textarea value={endReason} onChange={(e) => setEndReason(e.target.value)} maxLength={200} rows={2} />
          </Field>
          {endCoverage.isError && <Callout tone="danger">{errorMessage(endCoverage.error)}</Callout>}
        </div>
      </ConfirmDialog>
    </Drawer>
  );
}

export default function WorkersPage() {
  useDocumentTitle("Trabajadores");
  const { can } = useAuth();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<"active" | "inactive" | "all">("active");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const query = useDebounced(q.trim(), 350);
  const { data, isLoading } = useWorkerSearch({
    q: query || undefined,
    active: status === "all" ? undefined : status === "active",
    page,
    size: PAGE_SIZE,
  });

  const columns: Column<WorkerSummary>[] = [
    {
      key: "name",
      header: "Trabajador",
      cell: (w) => (
        <div>
          <p className="font-medium">
            {w.paternal_surname} {w.maternal_surname ?? ""}, {w.first_names}
          </p>
          <p className="tabular text-xs text-ink-soft">DNI {w.document_number}</p>
        </div>
      ),
    },
    { key: "department", header: "Dependencia", cell: (w) => w.department_name ?? "—", hideOnMobile: true },
    {
      key: "contact",
      header: "Correo",
      hideOnMobile: true,
      cell: (w) =>
        w.has_email ? (
          <Mail className="size-4 text-status-done" aria-label="Con correo" />
        ) : (
          <MailX className="size-4 text-status-waiting" aria-label="Sin correo" />
        ),
    },
    { key: "status", header: "Estado", cell: (w) => (w.is_active ? <Badge tone="success">Activo</Badge> : <Badge>Inactivo</Badge>) },
  ];

  return (
    <div>
      <PageHeader
        eyebrow="Gestión"
        title="Trabajadores"
        description="Relación institucional de trabajadores con EPS Rímac. La actualización masiva se realiza en Importaciones."
        actions={
          can("worker:manage") && (
            <Button onClick={() => setCreating(true)} icon={<Plus className="size-4" />}>
              Registrar trabajador
            </Button>
          )
        }
      />
      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-line p-4">
          <SearchInput
            value={q}
            onChange={(v) => {
              setQ(v);
              setPage(1);
            }}
            label="Buscar por DNI, apellidos, nombres o correo"
            className="w-full max-w-md"
          />
          <Segmented
            label="Estado"
            value={status}
            onChange={(v) => {
              setStatus(v);
              setPage(1);
            }}
            options={[
              { value: "active", label: "Activos" },
              { value: "inactive", label: "Inactivos" },
              { value: "all", label: "Todos" },
            ]}
          />
          {data && <p className="tabular ml-auto text-[13px] text-ink-soft">{data.total.toLocaleString("es-PE")} trabajadores</p>}
        </div>
        <DataTable
          columns={columns}
          rows={data?.items}
          rowKey={(w) => w.public_id}
          loading={isLoading}
          onRowClick={(w) => setSelected(w.public_id)}
          caption="Trabajadores"
          empty={{ icon: Users, title: "Sin resultados", description: "Pruebe con otro DNI o apellido." }}
        />
        {data && data.total > 0 && <Pagination page={page} size={PAGE_SIZE} total={data.total} onPageChange={setPage} />}
      </Card>
      <WorkerDetail id={selected} onClose={() => setSelected(null)} />
      {creating && <WorkerFormModal open onClose={() => setCreating(false)} />}
    </div>
  );
}
