import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, CalendarClock, CalendarOff, Gauge, History, MapPin, Plus, Settings2, Stethoscope, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";

import { api } from "@/shared/api/client";
import type { Availability, Closure, ScheduleRow, SettingVersion, SettingVersionIn, Site, SiteSettings } from "@/shared/api/types";
import { useAuth } from "@/shared/auth/AuthProvider";
import { useSite } from "@/shared/auth/SiteProvider";
import { addDaysIso, fmt, todayIso } from "@/shared/lib/format";
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
  DefinitionList,
  EmptyState,
  Field,
  Input,
  PageHeader,
  Skeleton,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  Textarea,
  Toggle,
  type Column,
} from "@/shared/ui";

import { DoctorsTab } from "./DoctorsTab";

const WEEKDAYS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];

function useInvalidateSite(siteId: number) {
  const queryClient = useQueryClient();
  return () => {
    for (const key of ["site-settings", "site-schedule", "site-closures", "availability", "queue", "sites"]) {
      void queryClient.invalidateQueries({ queryKey: [key] });
    }
    void siteId;
  };
}

// ------------------------------------------------------------------ configuración

function SettingsTab({ siteId }: { siteId: number }) {
  const invalidate = useInvalidateSite(siteId);
  const { data, isLoading } = useQuery({ queryKey: ["site-settings", siteId], queryFn: () => api.get<SiteSettings>(`/sites/${siteId}/settings`) });
  const [form, setForm] = useState<SettingVersionIn | null>(null);
  const save = useMutation({
    mutationFn: (body: SettingVersionIn) => api.post<SettingVersion>(`/sites/${siteId}/settings`, body),
    onSuccess: () => {
      notify.success("Configuración programada", "Aplicará desde la fecha indicada.");
      setForm(null);
      invalidate();
    },
  });

  if (isLoading || !data) return <Skeleton className="h-80" />;
  const c = data.current;
  const startForm = () =>
    setForm({
      valid_from: addDaysIso(todayIso(), 1),
      daily_capacity: c?.daily_capacity ?? 20,
      slot_minutes: c?.slot_minutes ?? 15,
      tolerance_minutes: c?.tolerance_minutes ?? 10,
      max_concurrent_in_service: c?.max_concurrent_in_service ?? 1,
      registration_cutoff_minutes: c?.registration_cutoff_minutes ?? 0,
      upcoming_notice_ahead: c?.upcoming_notice_ahead ?? 2,
      allow_reregister_after_no_show: c?.allow_reregister_after_no_show ?? false,
      allow_reregister_after_cancel: c?.allow_reregister_after_cancel ?? true,
      notifications_enabled: c?.notifications_enabled ?? true,
      change_reason: "",
    });
  const num = (key: keyof SettingVersionIn) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => (f ? { ...f, [key]: Number(e.target.value) } : f));

  const historyColumns: Column<SettingVersion>[] = [
    { key: "from", header: "Vigente desde", cell: (v) => <span className="tabular font-medium">{fmt.date(v.valid_from)}</span> },
    { key: "cap", header: "Capacidad", cell: (v) => v.daily_capacity },
    { key: "slot", header: "Turno", cell: (v) => <span className="whitespace-nowrap">{v.slot_minutes} min</span> },
    { key: "tol", header: "Tolerancia", cell: (v) => <span className="whitespace-nowrap">{v.tolerance_minutes} min</span> },
    { key: "reason", header: "Motivo del cambio", cell: (v) => <span className="text-ink-muted">{v.change_reason ?? "—"}</span>, hideOnMobile: true },
    {
      key: "state",
      header: "",
      cell: (v) =>
        v.id === c?.id ? <Badge tone="success">Vigente</Badge> : v.valid_from > todayIso() ? <Badge tone="info">Programada</Badge> : <Badge>Histórica</Badge>,
    },
  ];

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader
          title="Configuración vigente"
          description={c ? `Desde el ${fmt.date(c.valid_from)}` : "Sin configuración"}
          icon={<Settings2 className="size-[18px]" />}
          actions={!form && <Button onClick={startForm} icon={<Plus className="size-4" />}>Programar cambio</Button>}
        />
        {c && (
          <div className="grid gap-6 p-5 md:grid-cols-2">
            <DefinitionList
              items={[
                ["Capacidad diaria", <span className="font-semibold">{c.daily_capacity} atenciones</span>],
                ["Duración de turno", `${c.slot_minutes} minutos`],
                ["Tolerancia al llamado", `${c.tolerance_minutes} minutos`],
                ["Atenciones simultáneas", c.max_concurrent_in_service],
              ]}
            />
            <DefinitionList
              items={[
                ["Cierre de registros", c.registration_cutoff_minutes ? `${c.registration_cutoff_minutes} min antes del cierre` : "Al finalizar el horario"],
                ["Aviso de proximidad", c.upcoming_notice_ahead ? `Con ${c.upcoming_notice_ahead} persona(s) delante` : "Desactivado"],
                ["Re-registro tras no presentarse", c.allow_reregister_after_no_show ? "Permitido" : "No permitido"],
                ["Notificaciones por correo", c.notifications_enabled ? "Activadas" : "Desactivadas"],
              ]}
            />
          </div>
        )}
      </Card>

      {form && (
        <Card>
          <CardHeader
            title="Programar nueva configuración"
            description="Por regla, los cambios aplican desde mañana o una fecha posterior; el día en curso no se altera."
          />
          <form
            className="grid gap-5 p-5 md:grid-cols-2 xl:grid-cols-3"
            onSubmit={(e) => {
              e.preventDefault();
              save.mutate(form);
            }}
          >
            {save.isError && <Callout tone="danger" className="md:col-span-2 xl:col-span-3">{errorMessage(save.error)}</Callout>}
            <Field label="Vigente desde" required>
              <Input type="date" min={addDaysIso(todayIso(), 1)} value={form.valid_from} onChange={(e) => setForm({ ...form, valid_from: e.target.value })} />
            </Field>
            <Field label="Capacidad diaria" required hint="Atenciones por día (1–500).">
              <Input type="number" min={1} max={500} value={form.daily_capacity} onChange={num("daily_capacity")} />
            </Field>
            <Field label="Duración de turno (min)" required hint="Referencial para la hora estimada.">
              <Input type="number" min={5} max={120} step={5} value={form.slot_minutes} onChange={num("slot_minutes")} />
            </Field>
            <Field label="Tolerancia al llamado (min)" required hint="Luego puede marcarse «no presentado».">
              <Input type="number" min={0} max={120} value={form.tolerance_minutes} onChange={num("tolerance_minutes")} />
            </Field>
            <Field label="Atenciones simultáneas" hint="N.º de médicos/consultorios.">
              <Input type="number" min={1} max={10} value={form.max_concurrent_in_service} onChange={num("max_concurrent_in_service")} />
            </Field>
            <Field label="Cierre de registros (min antes)" hint="0 = hasta el fin del horario.">
              <Input type="number" min={0} max={480} value={form.registration_cutoff_minutes} onChange={num("registration_cutoff_minutes")} />
            </Field>
            <Field label="Aviso de proximidad" hint="Personas delante para avisar (0 = no avisar).">
              <Input type="number" min={0} max={20} value={form.upcoming_notice_ahead} onChange={num("upcoming_notice_ahead")} />
            </Field>
            <div className="space-y-4 rounded-xl border border-line p-4 md:col-span-2">
              <Toggle
                checked={Boolean(form.notifications_enabled)}
                onChange={(v) => setForm({ ...form, notifications_enabled: v })}
                label="Notificaciones por correo"
              />
              <Toggle
                checked={Boolean(form.allow_reregister_after_cancel)}
                onChange={(v) => setForm({ ...form, allow_reregister_after_cancel: v })}
                label="Permitir re-registro el mismo día tras cancelar"
              />
              <Toggle
                checked={Boolean(form.allow_reregister_after_no_show)}
                onChange={(v) => setForm({ ...form, allow_reregister_after_no_show: v })}
                label="Permitir re-registro el mismo día tras no presentarse"
              />
            </div>
            <Field label="Motivo del cambio" required className="md:col-span-2 xl:col-span-3">
              <Textarea value={form.change_reason} maxLength={300} rows={2} onChange={(e) => setForm({ ...form, change_reason: e.target.value })} />
            </Field>
            <div className="flex justify-end gap-2 md:col-span-2 xl:col-span-3">
              <Button variant="secondary" onClick={() => setForm(null)}>
                Cancelar
              </Button>
              <Button type="submit" loading={save.isPending} disabled={form.change_reason.trim().length < 3}>
                Programar configuración
              </Button>
            </div>
          </form>
        </Card>
      )}

      <Card>
        <CardHeader title="Historial de configuraciones" icon={<History className="size-[18px]" />} />
        <DataTable columns={historyColumns} rows={data.history} rowKey={(v) => v.id} />
      </Card>
    </div>
  );
}

// ------------------------------------------------------------------------ horario

type Block = { enabled: boolean; start: string; end: string };
type Week = Record<number, { AM: Block; PM: Block }>;

function toWeek(rows: ScheduleRow[]): Week {
  const week: Week = {};
  for (let d = 1; d <= 7; d++) {
    week[d] = { AM: { enabled: false, start: "08:00", end: "12:00" }, PM: { enabled: false, start: "14:00", end: "17:00" } };
  }
  for (const r of rows) {
    const block = r.block as "AM" | "PM";
    week[r.weekday]![block] = { enabled: true, start: r.start_time.slice(0, 5), end: r.end_time.slice(0, 5) };
  }
  return week;
}

function ScheduleTab({ siteId }: { siteId: number }) {
  const { data } = useQuery({ queryKey: ["site-schedule", siteId], queryFn: () => api.get<ScheduleRow[]>(`/sites/${siteId}/schedules`) });
  if (!data) return <Skeleton className="h-96" />;
  return <ScheduleEditor key={JSON.stringify(data)} siteId={siteId} rows={data} />;
}

function ScheduleEditor({ siteId, rows }: { siteId: number; rows: ScheduleRow[] }) {
  const invalidate = useInvalidateSite(siteId);
  const initial = useMemo(() => toWeek(rows), [rows]);
  const [week, setWeek] = useState<Week>(initial);
  const [validFrom, setValidFrom] = useState(addDaysIso(todayIso(), 1));
  const [reason, setReason] = useState("");

  const save = useMutation({
    mutationFn: () => {
      const blocks = Object.entries(week).flatMap(([day, b]) =>
        (["AM", "PM"] as const)
          .filter((k) => b[k].enabled)
          .map((k) => ({ weekday: Number(day), block: k, start_time: b[k].start, end_time: b[k].end })),
      );
      return api.put<ScheduleRow[]>(`/sites/${siteId}/schedules`, { valid_from: validFrom, blocks, change_reason: reason });
    },
    onSuccess: () => {
      notify.success("Horario programado", `Aplicará desde el ${fmt.date(validFrom)}.`);
      setReason("");
      invalidate();
    },
  });

  const update = (day: number, block: "AM" | "PM", patch: Partial<Block>) =>
    setWeek((w) => ({ ...w, [day]: { ...w[day]!, [block]: { ...w[day]![block], ...patch } } }));
  const dirty = JSON.stringify(week) !== JSON.stringify(initial);

  return (
    <Card>
      <CardHeader
        title="Horario semanal de atención"
        description="Bloques de mañana y tarde por día. Los cambios aplican desde la fecha indicada y quedan auditados."
        icon={<CalendarClock className="size-[18px]" />}
      />
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-sm">
          <thead>
            <tr className="border-b border-line bg-surface text-xs font-semibold tracking-wide text-ink-soft uppercase">
              <th scope="col" className="px-5 py-3 text-left">Día</th>
              <th scope="col" className="px-3 py-3 text-left">Mañana</th>
              <th scope="col" className="px-3 py-3 text-left">Tarde</th>
            </tr>
          </thead>
          <tbody>
            {WEEKDAYS.map((name, i) => {
              const day = i + 1;
              return (
                <tr key={day} className="border-b border-line">
                  <th scope="row" className="px-5 py-3 text-left font-medium">{name}</th>
                  {(["AM", "PM"] as const).map((block) => {
                    const b = week[day]![block];
                    return (
                      <td key={block} className="px-3 py-2.5">
                        <div className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            className="size-4 accent-brand-700"
                            checked={b.enabled}
                            aria-label={`${name} ${block === "AM" ? "mañana" : "tarde"}: atiende`}
                            onChange={(e) => update(day, block, { enabled: e.target.checked })}
                          />
                          <Input type="time" value={b.start} disabled={!b.enabled} className="h-9 w-28" aria-label="Inicio" onChange={(e) => update(day, block, { start: e.target.value })} />
                          <span className="text-ink-soft">–</span>
                          <Input type="time" value={b.end} disabled={!b.enabled} className="h-9 w-28" aria-label="Fin" onChange={(e) => update(day, block, { end: e.target.value })} />
                        </div>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="grid gap-4 p-5 md:grid-cols-[200px_1fr_auto] md:items-end">
        <Field label="Vigente desde" required>
          <Input type="date" min={addDaysIso(todayIso(), 1)} value={validFrom} onChange={(e) => setValidFrom(e.target.value)} />
        </Field>
        <Field label="Motivo del cambio" required>
          <Input value={reason} maxLength={300} onChange={(e) => setReason(e.target.value)} placeholder="Ej.: nuevo horario del médico de la Clínica" />
        </Field>
        <Button onClick={() => save.mutate()} loading={save.isPending} disabled={!dirty || reason.trim().length < 3}>
          Programar horario
        </Button>
        {save.isError && <Callout tone="danger" className="md:col-span-3">{errorMessage(save.error)}</Callout>}
      </div>
    </Card>
  );
}

// ------------------------------------------------------------------------ cierres

function ClosuresTab({ siteId }: { siteId: number }) {
  const invalidate = useInvalidateSite(siteId);
  const { data, isLoading } = useQuery({ queryKey: ["site-closures", siteId], queryFn: () => api.get<Closure[]>(`/sites/${siteId}/closures`) });
  const [date, setDate] = useState(addDaysIso(todayIso(), 1));
  const [reason, setReason] = useState("");
  const [removing, setRemoving] = useState<Closure | null>(null);
  const add = useMutation({
    mutationFn: () => api.post<Closure>(`/sites/${siteId}/closures`, { closure_date: date, reason }),
    onSuccess: () => (notify.success("Cierre registrado"), setReason(""), invalidate()),
    onError: (e) => notify.error(e),
  });
  const remove = useMutation({
    mutationFn: (id: number) => api.delete(`/sites/${siteId}/closures/${id}`),
    onSuccess: () => (notify.success("Cierre eliminado"), setRemoving(null), invalidate()),
    onError: (e) => notify.error(e),
  });

  return (
    <Card>
      <CardHeader title="Días sin atención" description="Feriados, cierres o ausencia del personal médico. Se bloquea el registro en esas fechas." icon={<CalendarOff className="size-[18px]" />} />
      <div className="grid gap-3 border-b border-line p-5 md:grid-cols-[200px_1fr_auto] md:items-end">
        <Field label="Fecha">
          <Input type="date" min={todayIso()} value={date} onChange={(e) => setDate(e.target.value)} />
        </Field>
        <Field label="Motivo">
          <Input value={reason} maxLength={200} onChange={(e) => setReason(e.target.value)} placeholder="Ej.: Feriado nacional" />
        </Field>
        <Button onClick={() => add.mutate()} loading={add.isPending} disabled={reason.trim().length < 3} icon={<Plus className="size-4" />}>
          Registrar cierre
        </Button>
      </div>
      {isLoading ? (
        <Skeleton className="m-5 h-24" />
      ) : data?.length === 0 ? (
        <EmptyState icon={CalendarOff} title="Sin cierres programados" />
      ) : (
        <ul>
          {data?.map((c) => (
            <li key={c.id} className="flex items-center gap-4 border-b border-line px-5 py-3 last:border-b-0">
              <span className="tabular w-28 font-semibold">{fmt.date(c.closure_date)}</span>
              <span className="flex-1 text-ink-muted">{c.reason}</span>
              <Button size="sm" variant="ghost" icon={<Trash2 className="size-4" />} onClick={() => setRemoving(c)}>
                Eliminar
              </Button>
            </li>
          ))}
        </ul>
      )}
      <ConfirmDialog
        open={Boolean(removing)}
        onOpenChange={(o) => !o && setRemoving(null)}
        tone="danger"
        title="Eliminar cierre"
        description={removing ? `Se habilitará nuevamente el registro para el ${fmt.date(removing.closure_date)}.` : undefined}
        confirmLabel="Eliminar"
        loading={remove.isPending}
        onConfirm={() => removing && remove.mutate(removing.id)}
      />
    </Card>
  );
}

// ------------------------------------------------------------ capacidad del día

function CapacityTab({ siteId }: { siteId: number }) {
  const invalidate = useInvalidateSite(siteId);
  const [date, setDate] = useState(todayIso());
  const { data } = useQuery({
    queryKey: ["availability", siteId, date],
    queryFn: () => api.get<Availability>(`/sites/${siteId}/availability`, { date }),
  });
  const [capacity, setCapacity] = useState<number | "">("");
  const [reason, setReason] = useState("");
  const adjust = useMutation({
    mutationFn: () => api.patch<Availability>(`/sites/${siteId}/service-days/${date}/capacity`, { capacity, reason }),
    onSuccess: () => (notify.success("Capacidad ajustada", "El cambio quedó auditado."), setReason(""), setCapacity(""), invalidate()),
  });
  return (
    <Card>
      <CardHeader
        title="Ajuste de capacidad de un día"
        description="Para situaciones puntuales (p. ej., el médico atenderá medio día). No modifica la configuración general."
        icon={<Gauge className="size-[18px]" />}
      />
      <div className="grid gap-5 p-5 md:grid-cols-2">
        <div className="space-y-4">
          <Field label="Fecha">
            <Input type="date" min={todayIso()} value={date} onChange={(e) => setDate(e.target.value)} />
          </Field>
          {data && (
            <DefinitionList
              items={[
                ["Capacidad actual", <span className="font-semibold">{data.capacity}</span>],
                ["Cupos ocupados", data.occupied],
                ["Disponibles", data.available],
              ]}
            />
          )}
        </div>
        <div className="space-y-4">
          <Field label="Nueva capacidad" hint={data ? `No puede ser menor que ${data.occupied} (cupos ocupados).` : undefined}>
            <Input type="number" min={data?.occupied ?? 0} max={500} value={capacity} onChange={(e) => setCapacity(e.target.value === "" ? "" : Number(e.target.value))} />
          </Field>
          <Field label="Motivo" required>
            <Textarea rows={2} maxLength={300} value={reason} onChange={(e) => setReason(e.target.value)} />
          </Field>
          {adjust.isError && <Callout tone="danger">{errorMessage(adjust.error)}</Callout>}
          <Button onClick={() => adjust.mutate()} loading={adjust.isPending} disabled={capacity === "" || reason.trim().length < 3}>
            Ajustar capacidad
          </Button>
        </div>
      </div>
    </Card>
  );
}

// --------------------------------------------------------------------- datos

function SiteDataTab({ site }: { site: Site }) {
  const invalidate = useInvalidateSite(site.id);
  const [form, setForm] = useState({ name: site.name, short_name: site.short_name, address: site.address ?? "", location_note: site.location_note ?? "" });
  const save = useMutation({
    mutationFn: () => api.patch<Site>(`/sites/${site.id}`, { ...form, address: form.address || null, location_note: form.location_note || null }),
    onSuccess: () => (notify.success("Datos de la sede actualizados"), invalidate()),
    onError: (e) => notify.error(e),
  });
  return (
    <Card>
      <CardHeader title="Datos de la sede" icon={<MapPin className="size-[18px]" />} />
      <div className="grid gap-4 p-5 md:grid-cols-2">
        <Field label="Nombre">
          <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </Field>
        <Field label="Nombre corto" hint="Se muestra en el selector de sede.">
          <Input value={form.short_name} onChange={(e) => setForm({ ...form, short_name: e.target.value })} />
        </Field>
        <Field label="Dirección">
          <Input value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />
        </Field>
        <Field label="Ubicación del tópico" hint="Se incluye en el correo de llamado (p. ej., «Primer piso, junto a Mesa de Partes»).">
          <Input value={form.location_note} onChange={(e) => setForm({ ...form, location_note: e.target.value })} />
        </Field>
        <div className="flex items-center justify-between md:col-span-2">
          <p className="text-[13px] text-ink-soft">
            Prefijo de turnos: <Badge tone="brand">{site.ticket_prefix}-001</Badge>
          </p>
          <Button onClick={() => save.mutate()} loading={save.isPending}>
            Guardar
          </Button>
        </div>
      </div>
    </Card>
  );
}

export default function SitesPage() {
  useDocumentTitle("Sedes y horarios");
  const { can } = useAuth();
  const { site: currentSite } = useSite();
  const { data: sites } = useQuery({ queryKey: ["sites"], queryFn: () => api.get<Site[]>("/sites") });
  const site = sites?.find((s) => s.id === currentSite?.id);

  return (
    <div>
      <PageHeader
        eyebrow="Administración"
        title="Sedes y horarios"
        description={
          site
            ? `${site.name} · para configurar otra sede, cámbiela en el selector superior. Ningún valor está fijado en el código.`
            : "Parámetros operativos por sede."
        }
      />
      {!site ? (
        <Skeleton className="h-96" />
      ) : (
        <Tabs defaultValue="settings" key={site.id}>
          <TabsList>
            <TabsTrigger value="settings">
              <Settings2 className="size-4" /> Configuración
            </TabsTrigger>
            <TabsTrigger value="schedule">
              <CalendarClock className="size-4" /> Horario
            </TabsTrigger>
            <TabsTrigger value="doctors">
              <Stethoscope className="size-4" /> Médicos
            </TabsTrigger>
            <TabsTrigger value="closures">
              <CalendarOff className="size-4" /> Cierres
            </TabsTrigger>
            {can("service_day:adjust") && (
              <TabsTrigger value="capacity">
                <Gauge className="size-4" /> Capacidad del día
              </TabsTrigger>
            )}
            <TabsTrigger value="data">
              <Building2 className="size-4" /> Datos de la sede
            </TabsTrigger>
          </TabsList>
          <TabsContent value="settings">
            <SettingsTab siteId={site.id} />
          </TabsContent>
          <TabsContent value="schedule">
            <ScheduleTab siteId={site.id} />
          </TabsContent>
          <TabsContent value="doctors">
            <DoctorsTab siteId={site.id} />
          </TabsContent>
          <TabsContent value="closures">
            <ClosuresTab siteId={site.id} />
          </TabsContent>
          <TabsContent value="capacity">
            <CapacityTab siteId={site.id} />
          </TabsContent>
          <TabsContent value="data">
            <SiteDataTab key={JSON.stringify(site)} site={site} />
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
