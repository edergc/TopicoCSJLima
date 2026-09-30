import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Copy,
  Download,
  FileSpreadsheet,
  FileUp,
  History,
  PencilLine,
  Sparkles,
  Trash2,
  XCircle,
} from "lucide-react";
import { useRef, useState, type DragEvent } from "react";

import { api } from "@/shared/api/client";
import type { ImportBatch, ImportRow, Page } from "@/shared/api/types";
import { cn } from "@/shared/lib/cn";
import { fmt } from "@/shared/lib/format";
import { useDocumentTitle } from "@/shared/lib/hooks";
import { errorMessage, notify } from "@/shared/lib/notify";
import {
  Badge,
  Button,
  Callout,
  Card,
  CardHeader,
  ConfirmDialog,
  DataTable,
  KpiCard,
  PageHeader,
  Pagination,
  Segmented,
  Toggle,
  type Column,
} from "@/shared/ui";

const OUTCOME: Record<string, { label: string; tone: "success" | "info" | "neutral" | "danger" | "warning" }> = {
  NEW: { label: "Nuevo", tone: "success" },
  UPDATE: { label: "Actualiza", tone: "info" },
  UNCHANGED: { label: "Sin cambios", tone: "neutral" },
  ERROR: { label: "Error", tone: "danger" },
  DUPLICATE_IN_FILE: { label: "Duplicado", tone: "warning" },
};

const BATCH_STATUS: Record<string, { label: string; tone: "success" | "info" | "neutral" | "danger" }> = {
  UPLOADED: { label: "Cargado", tone: "info" },
  VALIDATED: { label: "Validado · pendiente", tone: "info" },
  CONFIRMED: { label: "Confirmado", tone: "success" },
  DISCARDED: { label: "Descartado", tone: "neutral" },
  FAILED: { label: "Fallido", tone: "danger" },
};

const FIELD_LABEL: Record<string, string> = {
  first_names: "Nombres",
  paternal_surname: "Ap. paterno",
  maternal_surname: "Ap. materno",
  sex: "Sexo",
  birth_date: "F. nacimiento",
  institutional_email: "Correo",
  phone: "Teléfono",
  department_name: "Dependencia",
  employee_code: "Código",
  is_active: "Estado",
  coverage: "Cobertura",
};

const ROWS_PAGE = 50;

function Dropzone({ onFile, loading }: { onFile: (file: File) => void; loading: boolean }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    const file = e.dataTransfer.files[0];
    if (file) onFile(file);
  };
  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={onDrop}
      className={cn(
        "flex flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-14 text-center transition-colors",
        over ? "border-brand-600 bg-brand-50/50" : "border-line-strong bg-surface/50",
      )}
    >
      <div className="grid size-14 place-items-center rounded-2xl bg-panel shadow-[var(--shadow-card)] ring-1 ring-line">
        <FileSpreadsheet className="size-7 text-status-done" aria-hidden />
      </div>
      <p className="mt-4 text-[15px] font-semibold">Arrastre aquí el Excel de trabajadores con EPS Rímac</p>
      <p className="mt-1 max-w-md text-sm text-ink-soft">
        Formato .xlsx. Se reconocen columnas como DNI, APELLIDO PATERNO, APELLIDO MATERNO, NOMBRES, CORREO, SEXO,
        DEPENDENCIA y FECHA DE NACIMIENTO. Nada se incorpora hasta que usted confirme.
      </p>
      <input
        ref={inputRef}
        type="file"
        accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        className="sr-only"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onFile(file);
          e.target.value = "";
        }}
      />
      <Button className="mt-5" loading={loading} onClick={() => inputRef.current?.click()} icon={<FileUp className="size-4" />}>
        {loading ? "Validando archivo…" : "Seleccionar archivo"}
      </Button>
    </div>
  );
}

function RowDetail({ row }: { row: ImportRow }) {
  const n = row.normalized ?? {};
  const name = [n.paternal_surname, n.maternal_surname].filter(Boolean).join(" ");
  return (
    <div className="min-w-0 space-y-1">
      <p className="truncate font-medium">{name ? `${name}, ${String(n.first_names ?? "")}` : "—"}</p>
      {row.errors.map((e) => (
        <p key={e} className="flex items-start gap-1.5 text-xs text-danger">
          <XCircle className="mt-px size-3.5 shrink-0" aria-hidden /> {e}
        </p>
      ))}
      {row.warnings.map((w) => (
        <p key={w} className="flex items-start gap-1.5 text-xs text-status-waiting">
          <AlertTriangle className="mt-px size-3.5 shrink-0" aria-hidden /> {w}
        </p>
      ))}
      {row.changes &&
        Object.entries(row.changes).map(([field, change]) => {
          const [before, after] = change as [unknown, unknown];
          return (
            <p key={field} className="flex items-start gap-1.5 text-xs text-status-called">
              <PencilLine className="mt-px size-3.5 shrink-0" aria-hidden />
              <span>
                {FIELD_LABEL[field] ?? field}: <span className="line-through opacity-70">{String(before ?? "vacío")}</span> →{" "}
                <span className="font-medium">{String(after ?? "vacío")}</span>
              </span>
            </p>
          );
        })}
    </div>
  );
}

function BatchReview({ batch, onBack }: { batch: ImportBatch; onBack: () => void }) {
  const queryClient = useQueryClient();
  const [outcome, setOutcome] = useState("");
  const [page, setPage] = useState(1);
  const [confirming, setConfirming] = useState(false);
  const [deactivateMissing, setDeactivateMissing] = useState(false);
  const pending = batch.status === "VALIDATED";

  const rows = useQuery({
    queryKey: ["import-rows", batch.public_id, outcome, page],
    queryFn: () => api.get<Page<ImportRow>>(`/imports/${batch.public_id}/rows`, { outcome, page, size: ROWS_PAGE }),
    placeholderData: keepPreviousData,
  });
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["imports"] });
  const confirm = useMutation({
    mutationFn: () => api.post<ImportBatch>(`/imports/${batch.public_id}/confirm`, { deactivate_missing: deactivateMissing }),
    onSuccess: (result) => {
      notify.success("Importación confirmada", `${result.new_count} nuevos · ${result.update_count} actualizados · ${result.deactivated_count} coberturas terminadas`);
      queryClient.setQueryData(["import", batch.public_id], result);
      setConfirming(false);
      refresh();
      void queryClient.invalidateQueries({ queryKey: ["workers"] });
    },
    onError: (e) => notify.error(e),
  });
  const discard = useMutation({
    mutationFn: () => api.post<ImportBatch>(`/imports/${batch.public_id}/discard`),
    onSuccess: () => {
      notify.info("Lote descartado");
      refresh();
      onBack();
    },
    onError: (e) => notify.error(e),
  });

  const columns: Column<ImportRow>[] = [
    { key: "row", header: "Fila", cell: (r) => <span className="tabular text-ink-soft">{r.row_number}</span>, className: "w-16" },
    {
      key: "dni",
      header: "DNI",
      cell: (r) => <span className="tabular font-medium">{String(r.normalized?.document_number ?? "—")}</span>,
      className: "w-28",
    },
    { key: "detail", header: "Datos y observaciones", cell: (r) => <RowDetail row={r} /> },
    {
      key: "outcome",
      header: "Resultado",
      cell: (r) => <Badge tone={OUTCOME[r.outcome]?.tone ?? "neutral"}>{OUTCOME[r.outcome]?.label ?? r.outcome}</Badge>,
      className: "w-32",
    },
  ];
  const status = BATCH_STATUS[batch.status] ?? { label: batch.status, tone: "neutral" as const };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="ghost" onClick={onBack} icon={<ArrowLeft className="size-4" />}>
          Volver
        </Button>
        <div className="min-w-0">
          <p className="flex items-center gap-2 font-semibold">
            <FileSpreadsheet className="size-4 text-status-done" aria-hidden /> {batch.file_name}
            <Badge tone={status.tone}>{status.label}</Badge>
          </p>
          <p className="text-xs text-ink-soft">
            Hoja «{batch.sheet_name}» · cargado {fmt.dateTime(batch.created_at)}
          </p>
        </div>
        <div className="ml-auto flex flex-wrap gap-2">
          <Button
            variant="secondary"
            icon={<Download className="size-4" />}
            onClick={() => void api.download(`/imports/${batch.public_id}/errors.csv`).catch((e) => notify.error(e))}
          >
            Reporte de observaciones
          </Button>
          {pending && (
            <>
              <Button variant="ghost" onClick={() => discard.mutate()} loading={discard.isPending} icon={<Trash2 className="size-4" />}>
                Descartar
              </Button>
              <Button onClick={() => setConfirming(true)} icon={<CheckCircle2 className="size-4" />}>
                Confirmar importación
              </Button>
            </>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <KpiCard label="Nuevos" value={batch.new_count} icon={Sparkles} tone="done" />
        <KpiCard label="Actualizan" value={batch.update_count} icon={PencilLine} tone="called" />
        <KpiCard label="Sin cambios" value={batch.unchanged_count} icon={Copy} />
        <KpiCard label="Duplicados" value={batch.duplicate_count} icon={AlertTriangle} tone="waiting" />
        <KpiCard label="Con error" value={batch.error_count} icon={XCircle} tone={batch.error_count ? "danger" : "neutral"} />
      </div>

      {batch.error_count > 0 && pending && (
        <Callout tone="warning" title="Hay filas con error">
          Las filas con error o duplicadas no se incorporarán. Puede corregir el Excel y volver a cargarlo, o confirmar
          solo las filas válidas.
        </Callout>
      )}
      {batch.status === "CONFIRMED" && (
        <Callout tone="success" title="Importación aplicada">
          Confirmada el {fmt.dateTime(batch.confirmed_at)}.{" "}
          {batch.deactivated_count > 0 && `${batch.deactivated_count} cobertura(s) terminada(s) por no figurar en la relación.`}
        </Callout>
      )}

      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-line p-4">
          <Segmented
            label="Filtrar por resultado"
            value={outcome}
            onChange={(v) => {
              setOutcome(v);
              setPage(1);
            }}
            options={[
              { value: "", label: `Todas (${batch.total_rows})` },
              { value: "ERROR", label: `Errores (${batch.error_count})` },
              { value: "NEW", label: `Nuevos (${batch.new_count})` },
              { value: "UPDATE", label: `Actualizan (${batch.update_count})` },
              { value: "DUPLICATE_IN_FILE", label: `Duplicados (${batch.duplicate_count})` },
            ]}
          />
        </div>
        <DataTable columns={columns} rows={rows.data?.items} rowKey={(r) => r.row_number} loading={rows.isLoading} caption="Filas del archivo" />
        {rows.data && rows.data.total > ROWS_PAGE && (
          <Pagination page={page} size={ROWS_PAGE} total={rows.data.total} onPageChange={setPage} />
        )}
      </Card>

      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title="Confirmar importación"
        description="Los cambios se aplican en una sola operación y quedan registrados en la auditoría."
        confirmLabel="Confirmar e incorporar"
        loading={confirm.isPending}
        onConfirm={() => confirm.mutate()}
      >
        <div className="space-y-4">
          <ul className="space-y-1 text-sm">
            <li>
              <span className="tabular font-semibold">{batch.new_count}</span> trabajadores nuevos con cobertura EPS Rímac
            </li>
            <li>
              <span className="tabular font-semibold">{batch.update_count}</span> trabajadores con datos actualizados
            </li>
            <li className="text-ink-soft">
              {batch.error_count + batch.duplicate_count} filas se omiten (error o duplicado)
            </li>
          </ul>
          <div className="rounded-xl border border-line p-3">
            <Toggle
              checked={deactivateMissing}
              onChange={setDeactivateMissing}
              label="Terminar la cobertura de quienes no figuran en este archivo"
              description="Úselo solo si el archivo es la relación COMPLETA vigente de trabajadores con EPS Rímac."
            />
          </div>
          {deactivateMissing && (
            <Callout tone="warning">Los trabajadores que no aparecen en el archivo dejarán de estar habilitados para registrar atenciones.</Callout>
          )}
        </div>
      </ConfirmDialog>
    </div>
  );
}

export default function ImportsPage() {
  useDocumentTitle("Importaciones");
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const history = useQuery({
    queryKey: ["imports", page],
    queryFn: () => api.get<Page<ImportBatch>>("/imports", { page, size: 10 }),
    placeholderData: keepPreviousData,
  });
  const batch = useQuery({
    queryKey: ["import", selected],
    queryFn: () => api.get<ImportBatch>(`/imports/${selected}`),
    enabled: Boolean(selected),
  });
  const upload = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      form.append("kind", "WORKERS_EPS");
      return api.post<ImportBatch>("/imports", form);
    },
    onSuccess: (result) => {
      queryClient.setQueryData(["import", result.public_id], result);
      setSelected(result.public_id);
      void queryClient.invalidateQueries({ queryKey: ["imports"] });
    },
  });

  if (selected && batch.data) {
    return (
      <div>
        <PageHeader eyebrow="Gestión" title="Revisión de importación" />
        <BatchReview batch={batch.data} onBack={() => setSelected(null)} />
      </div>
    );
  }

  const columns: Column<ImportBatch>[] = [
    { key: "file", header: "Archivo", cell: (b) => <span className="font-medium">{b.file_name}</span> },
    { key: "date", header: "Cargado", cell: (b) => <span className="tabular">{fmt.dateTime(b.created_at)}</span>, hideOnMobile: true },
    {
      key: "summary",
      header: "Resumen",
      hideOnMobile: true,
      cell: (b) => (
        <span className="tabular text-[13px] text-ink-muted">
          {b.total_rows} filas · {b.new_count} nuevos · {b.update_count} act. · {b.error_count} errores
        </span>
      ),
    },
    {
      key: "status",
      header: "Estado",
      cell: (b) => <Badge tone={BATCH_STATUS[b.status]?.tone ?? "neutral"}>{BATCH_STATUS[b.status]?.label ?? b.status}</Badge>,
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Gestión"
        title="Importaciones"
        description="Actualice la relación de trabajadores con EPS Rímac desde el Excel institucional. El proceso valida, muestra una vista previa y solo aplica los cambios cuando usted confirma."
      />
      {upload.isError && <Callout tone="danger" title="No se pudo procesar el archivo">{errorMessage(upload.error)}</Callout>}
      <Dropzone onFile={(file) => upload.mutate(file)} loading={upload.isPending} />
      <Card>
        <CardHeader title="Historial de importaciones" icon={<History className="size-[18px]" />} />
        <DataTable
          columns={columns}
          rows={history.data?.items}
          rowKey={(b) => b.public_id}
          loading={history.isLoading}
          onRowClick={(b) => setSelected(b.public_id)}
          empty={{ icon: FileSpreadsheet, title: "Aún no hay importaciones" }}
        />
        {history.data && history.data.total > 10 && (
          <Pagination page={page} size={10} total={history.data.total} onPageChange={setPage} />
        )}
      </Card>
    </div>
  );
}
