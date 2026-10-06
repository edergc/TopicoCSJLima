import { Eye, ListChecks, Mail, Plus, Save, SlidersHorizontal, Palette } from "lucide-react";
import { useState } from "react";

import type { Parameter, ReasonAdmin, Template } from "@/shared/api/types";
import { useAuth } from "@/shared/auth/AuthProvider";
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
  DataTable,
  Field,
  Input,
  Modal,
  PageHeader,
  Select,
  Skeleton,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  Textarea,
  Toggle,
  type Column,
} from "@/shared/ui";

import { BrandingTab } from "./BrandingTab";
import { useAdminReasons, useParameters, useSaveReason, useSaveTemplate, useTemplatePreview, useTemplates, useUpdateParameter } from "./api";

const REASON_TYPE: Record<string, string> = {
  CANCEL: "Cancelación",
  VOID: "Anulación",
  NO_SHOW: "No presentado",
  REQUEUE: "Devolución a la cola",
  PRIORITY: "Prioridad (categoría)",
};

const TEMPLATE_VARIABLES = [
  ["worker_first_name", "Primer nombre del trabajador"],
  ["ticket_code", "Código de turno (A-007)"],
  ["site_name", "Nombre de la sede"],
  ["location_note", "Ubicación del tópico"],
  ["service_date", "Fecha de atención"],
  ["registered_time", "Hora de registro"],
  ["people_ahead", "Personas delante"],
  ["estimated_time", "Hora estimada"],
  ["reason_label", "Motivo (cancelación)"],
  ["institution_name", "Nombre de la institución"],
] as const;

// ------------------------------------------------------------------------ motivos

function ReasonModal({ reason, onClose }: { reason: ReasonAdmin | "new"; onClose: () => void }) {
  const isNew = reason === "new";
  const save = useSaveReason();
  const [form, setForm] = useState({
    type: isNew ? "CANCEL" : reason.type,
    code: isNew ? "" : reason.code,
    label: isNew ? "" : reason.label,
    requires_note: isNew ? false : reason.requires_note,
    is_active: isNew ? true : reason.is_active,
    sort_order: isNew ? 50 : reason.sort_order,
  });
  const submit = () => {
    const body = isNew
      ? { type: form.type, code: form.code.toUpperCase(), label: form.label, requires_note: form.requires_note, sort_order: form.sort_order }
      : { label: form.label, requires_note: form.requires_note, is_active: form.is_active, sort_order: form.sort_order };
    save.mutate({ id: isNew ? undefined : reason.id, body }, { onSuccess: () => (notify.success("Motivo guardado"), onClose()) });
  };
  return (
    <Modal
      open
      onOpenChange={(o) => !o && onClose()}
      title={isNew ? "Nuevo motivo" : "Editar motivo"}
      description="Los motivos son administrativos. Nunca registre motivos clínicos."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button onClick={submit} loading={save.isPending} disabled={form.label.trim().length < 3 || (isNew && !/^[A-Z][A-Z0-9_]{1,39}$/.test(form.code.toUpperCase()))}>
            Guardar
          </Button>
        </>
      }
    >
      <div className="grid gap-4 sm:grid-cols-2">
        {save.isError && <Callout tone="danger" className="sm:col-span-2">{errorMessage(save.error)}</Callout>}
        <Field label="Tipo">
          <Select value={form.type} disabled={!isNew} onChange={(e) => setForm({ ...form, type: e.target.value })}>
            {Object.entries(REASON_TYPE).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Código" hint="Mayúsculas y guiones bajos.">
          <Input value={form.code} disabled={!isNew} onChange={(e) => setForm({ ...form, code: e.target.value.toUpperCase().replace(/\s/g, "_") })} />
        </Field>
        <Field label="Texto visible" className="sm:col-span-2">
          <Input value={form.label} maxLength={150} onChange={(e) => setForm({ ...form, label: e.target.value })} />
        </Field>
        <Field label="Orden">
          <Input type="number" min={0} max={999} value={form.sort_order} onChange={(e) => setForm({ ...form, sort_order: Number(e.target.value) })} />
        </Field>
        <div className="space-y-3 sm:col-span-2">
          <Toggle checked={form.requires_note} onChange={(v) => setForm({ ...form, requires_note: v })} label="Exige observación" description="Para motivos genéricos como «Otro»." />
          {!isNew && <Toggle checked={form.is_active} onChange={(v) => setForm({ ...form, is_active: v })} label="Activo" description="Los inactivos no se ofrecen, pero se conservan en el historial." />}
        </div>
      </div>
    </Modal>
  );
}

function ReasonsTab() {
  const { data, isLoading } = useAdminReasons();
  const [editing, setEditing] = useState<ReasonAdmin | "new" | null>(null);
  const columns: Column<ReasonAdmin>[] = [
    { key: "type", header: "Tipo", cell: (r) => <Badge tone="brand">{REASON_TYPE[r.type] ?? r.type}</Badge> },
    { key: "label", header: "Motivo", cell: (r) => <span className="font-medium">{r.label}</span> },
    { key: "code", header: "Código", cell: (r) => <span className="font-mono text-xs text-ink-soft">{r.code}</span>, hideOnMobile: true },
    { key: "note", header: "Observación", cell: (r) => (r.requires_note ? "Obligatoria" : "Opcional"), hideOnMobile: true },
    { key: "active", header: "Estado", cell: (r) => (r.is_active ? <Badge tone="success">Activo</Badge> : <Badge>Inactivo</Badge>) },
  ];
  return (
    <Card>
      <CardHeader
        title="Motivos administrativos"
        description="Opciones que se ofrecen al cancelar, anular, marcar no presentado o devolver a la cola."
        actions={<Button onClick={() => setEditing("new")} icon={<Plus className="size-4" />}>Nuevo motivo</Button>}
      />
      <DataTable columns={columns} rows={data} rowKey={(r) => r.id} loading={isLoading} onRowClick={setEditing} />
      {editing && <ReasonModal reason={editing} onClose={() => setEditing(null)} />}
    </Card>
  );
}

// ---------------------------------------------------------------------- plantillas

const TEMPLATE_NAME: Record<string, string> = {
  APPT_REGISTERED: "Confirmación de registro",
  APPT_UPCOMING: "Aviso de proximidad",
  APPT_CALLED: "Llamado al tópico",
  APPT_CANCELLED: "Cancelación",
};

function TemplatesTab() {
  const { data, isLoading } = useTemplates();
  const save = useSaveTemplate();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const selected = data?.find((t) => t.id === selectedId) ?? data?.[0];

  if (isLoading || !data || !selected) return <Skeleton className="h-96" />;

  return (
    <div className="grid gap-6 lg:grid-cols-[260px_minmax(0,1fr)]">
      <Card className="h-fit p-2">
        <ul>
          {data.map((t) => (
            <li key={t.id}>
              <button
                type="button"
                onClick={() => setSelectedId(t.id)}
                className={cn(
                  "flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-left text-sm",
                  t.id === selected.id ? "bg-brand-50 font-medium text-brand-900" : "text-ink-muted hover:bg-surface",
                )}
              >
                <Mail className="size-4 shrink-0" aria-hidden />
                <span className="flex-1">{TEMPLATE_NAME[t.code] ?? t.code}</span>
                {!t.is_active && <Badge>Inactiva</Badge>}
              </button>
            </li>
          ))}
        </ul>
      </Card>
      <TemplateEditor key={`${selected.id}-${selected.updated_at}`} template={selected} save={save} />
    </div>
  );
}

function TemplateEditor({ template: selected, save }: { template: Template; save: ReturnType<typeof useSaveTemplate> }) {
  const [draft, setDraft] = useState<Pick<Template, "subject" | "body_text" | "is_active">>({
    subject: selected.subject,
    body_text: selected.body_text,
    is_active: selected.is_active,
  });
  const [previewing, setPreviewing] = useState(false);
  const preview = useTemplatePreview(previewing ? selected.id : null);
  const dirty = draft.subject !== selected.subject || draft.body_text !== selected.body_text || draft.is_active !== selected.is_active;

  return (
    <>
      <Card>
        <CardHeader
          title={TEMPLATE_NAME[selected.code] ?? selected.code}
          description={`${selected.description} · actualizada ${fmt.dateTime(selected.updated_at)}`}
          actions={
            <>
              <Button variant="secondary" onClick={() => setPreviewing(true)} disabled={dirty} icon={<Eye className="size-4" />}>
                Vista previa
              </Button>
              <Button
                disabled={!dirty}
                loading={save.isPending}
                icon={<Save className="size-4" />}
                onClick={() => save.mutate({ id: selected.id, body: draft }, { onSuccess: () => notify.success("Plantilla guardada"), onError: (e) => notify.error(e) })}
              >
                Guardar
              </Button>
            </>
          }
        />
        <div className="grid gap-5 p-5 xl:grid-cols-[minmax(0,1fr)_240px]">
          <div className="space-y-4">
            <Field label="Asunto">
              <Input value={draft.subject} maxLength={200} onChange={(e) => setDraft({ ...draft, subject: e.target.value })} />
            </Field>
            <Field label="Mensaje" hint="Use {{ variable }} para insertar datos. La sintaxis se valida al guardar.">
              <Textarea value={draft.body_text} rows={16} className="font-mono text-[0.8125rem]" onChange={(e) => setDraft({ ...draft, body_text: e.target.value })} />
            </Field>
            <Toggle checked={draft.is_active} onChange={(v) => setDraft({ ...draft, is_active: v })} label="Plantilla activa" description="Si se desactiva, este correo deja de enviarse." />
          </div>
          <div>
            <p className="mb-2 text-xs font-semibold tracking-wide text-ink-soft uppercase">Variables</p>
            <ul className="space-y-1.5 text-[0.8125rem]">
              {TEMPLATE_VARIABLES.map(([name, label]) => (
                <li key={name}>
                  <code className="rounded bg-sunken px-1.5 py-0.5 font-mono text-xs text-brand-800">{`{{ ${name} }}`}</code>
                  <p className="text-xs text-ink-soft">{label}</p>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </Card>
      {previewing && (
        <Modal open onOpenChange={(o) => !o && setPreviewing(false)} title="Vista previa" description="Con datos de ejemplo." size="lg">
          {preview.data ? (
            <div className="space-y-3">
              <p className="text-sm">
                <span className="text-ink-soft">Asunto: </span>
                <span className="font-semibold">{preview.data.subject}</span>
              </p>
              <pre className="rounded-xl border border-line bg-surface p-4 font-sans text-sm leading-relaxed whitespace-pre-wrap">{preview.data.body_text}</pre>
            </div>
          ) : (
            <Skeleton className="h-64" />
          )}
        </Modal>
      )}
    </>
  );
}

// ---------------------------------------------------------------------- parámetros

function ParameterRow({ param }: { param: Parameter }) {
  const update = useUpdateParameter();
  const [value, setValue] = useState<string>(String(param.value));
  const dirty = value !== String(param.value);
  const parsed = param.value_type === "int" ? Number(value) : param.value_type === "bool" ? value === "true" : value;
  const valid = param.value_type !== "int" || (/^\d+$/.test(value) && Number(value) >= 0);

  return (
    <div className="grid gap-3 border-b border-line px-5 py-4 last:border-b-0 md:grid-cols-[minmax(0,1fr)_260px_auto] md:items-center">
      <div>
        <p className="text-sm font-medium text-ink">{param.description}</p>
        <p className="font-mono text-[0.6875rem] text-ink-faint">{param.key}</p>
      </div>
      {param.value_type === "bool" ? (
        <Select value={value} disabled={!param.is_editable} onChange={(e) => setValue(e.target.value)} aria-label={param.description}>
          <option value="true">Sí</option>
          <option value="false">No</option>
        </Select>
      ) : (
        <Input
          value={value}
          disabled={!param.is_editable}
          inputMode={param.value_type === "int" ? "numeric" : undefined}
          aria-label={param.description}
          aria-invalid={!valid || undefined}
          onChange={(e) => setValue(e.target.value)}
        />
      )}
      <div className="flex justify-end">
        {param.is_editable ? (
          <Button
            size="sm"
            variant={dirty ? "primary" : "ghost"}
            disabled={!dirty || !valid}
            loading={update.isPending}
            onClick={() =>
              update.mutate({ key: param.key, value: parsed }, { onSuccess: () => notify.success("Parámetro actualizado"), onError: (e) => notify.error(e) })
            }
          >
            Guardar
          </Button>
        ) : (
          <Badge>Solo lectura</Badge>
        )}
      </div>
    </div>
  );
}

function ParametersTab() {
  const { data, isLoading } = useParameters();
  return (
    <Card>
      <CardHeader title="Parámetros del sistema" description="Valores globales. Cada cambio queda registrado en la auditoría." />
      {isLoading ? <Skeleton className="m-5 h-64" /> : data?.map((p) => <ParameterRow key={`${p.key}-${p.updated_at}`} param={p} />)}
    </Card>
  );
}

export default function ConfigurationPage() {
  useDocumentTitle("Catálogos y parámetros");
  const { can } = useAuth();
  const first = can("catalog:manage") ? "reasons" : can("template:manage") ? "templates" : "parameters";
  return (
    <div>
      <PageHeader eyebrow="Administración" title="Catálogos y parámetros" description="Motivos, plantillas de correo y parámetros generales, configurables sin modificar código." />
      <Tabs defaultValue={first}>
        <TabsList>
          {can("catalog:manage") && (
            <TabsTrigger value="reasons">
              <ListChecks className="size-4" /> Motivos
            </TabsTrigger>
          )}
          {can("template:manage") && (
            <TabsTrigger value="templates">
              <Mail className="size-4" /> Plantillas de correo
            </TabsTrigger>
          )}
          {can("parameter:manage") && (
            <TabsTrigger value="parameters">
              <SlidersHorizontal className="size-4" /> Parámetros
            </TabsTrigger>
          )}
          {can("parameter:manage") && (
            <TabsTrigger value="branding">
              <Palette className="size-4" /> Identidad visual
            </TabsTrigger>
          )}
        </TabsList>
        <TabsContent value="reasons">
          <ReasonsTab />
        </TabsContent>
        <TabsContent value="templates">
          <TemplatesTab />
        </TabsContent>
        <TabsContent value="parameters">
          <ParametersTab />
        </TabsContent>
        <TabsContent value="branding">
          <BrandingTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
