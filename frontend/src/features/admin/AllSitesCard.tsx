import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, MonitorPlay, Plus } from "lucide-react";
import { useState } from "react";

import { api } from "@/shared/api/client";
import type { Site, SiteCreateIn } from "@/shared/api/types";
import { useAuth } from "@/shared/auth/AuthProvider";
import { useSite } from "@/shared/auth/SiteProvider";
import { cn } from "@/shared/lib/cn";
import { todayIso } from "@/shared/lib/format";
import { notify } from "@/shared/lib/notify";
import { Badge, Button, Card, CardHeader, Field, Input, Modal, Skeleton, Toggle } from "@/shared/ui";

const DAYS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];

type Form = {
  name: string;
  short_name: string;
  code: string;
  ticket_prefix: string;
  address: string;
  location_note: string;
  valid_from: string;
  daily_capacity: number;
  slot_minutes: number;
  tolerance_minutes: number;
  days: boolean[];
  am: [string, string];
  pm_enabled: boolean;
  pm: [string, string];
};

const initialForm = (): Form => ({
  name: "",
  short_name: "",
  code: "",
  ticket_prefix: "",
  address: "",
  location_note: "",
  valid_from: todayIso(),
  daily_capacity: 20,
  slot_minutes: 15,
  tolerance_minutes: 10,
  days: [true, true, true, true, true, false, false],
  am: ["08:00", "12:00"],
  pm_enabled: true,
  pm: ["14:00", "17:00"],
});

function toPayload(f: Form): SiteCreateIn {
  const blocks: SiteCreateIn["blocks"] = [];
  f.days.forEach((on, i) => {
    if (!on) return;
    blocks.push({ weekday: i + 1, block: "AM", start_time: f.am[0], end_time: f.am[1] });
    if (f.pm_enabled) blocks.push({ weekday: i + 1, block: "PM", start_time: f.pm[0], end_time: f.pm[1] });
  });
  return {
    name: f.name.trim(),
    short_name: f.short_name.trim(),
    code: f.code,
    ticket_prefix: f.ticket_prefix,
    address: f.address.trim() || null,
    location_note: f.location_note.trim() || null,
    valid_from: f.valid_from,
    daily_capacity: f.daily_capacity,
    slot_minutes: f.slot_minutes,
    tolerance_minutes: f.tolerance_minutes,
    blocks,
  };
}

/** Administración de sedes: todas (incluidas las inactivas), alta de sedes nuevas y activación. */
export function AllSitesCard() {
  const { reloadUser } = useAuth();
  const { setSiteId } = useSite();
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["sites-all"], queryFn: () => api.get<Site[]>("/sites/all") });
  const [form, setForm] = useState<Form | null>(null);

  const refresh = async () => {
    await reloadUser();
    void queryClient.invalidateQueries({ queryKey: ["sites-all"] });
    void queryClient.invalidateQueries({ queryKey: ["display-sites"] });
  };

  const create = useMutation({
    mutationFn: (f: Form) => api.post<Site>("/sites", toPayload(f)),
    onSuccess: async (site) => {
      notify.success("Sede creada", `${site.name}: configure ahora sus consultorios y médicos.`);
      setForm(null);
      await refresh();
      setSiteId(site.id);
    },
    onError: (e) => notify.error(e),
  });
  const toggle = useMutation({
    mutationFn: (site: Site) => api.patch<Site>(`/sites/${site.id}`, { is_active: !site.is_active }),
    onSuccess: async (site) => {
      notify.success(site.is_active ? "Sede activada" : "Sede desactivada");
      await refresh();
    },
    onError: (e) => notify.error(e),
  });

  const set = (patch: Partial<Form>) => form && setForm({ ...form, ...patch });
  const valid =
    form !== null &&
    form.name.trim().length >= 3 &&
    form.short_name.trim().length >= 2 &&
    /^[A-Z]{2,10}$/.test(form.code) &&
    /^[A-Z]{1,3}$/.test(form.ticket_prefix) &&
    form.days.some(Boolean) &&
    form.am[0] < form.am[1] &&
    (!form.pm_enabled || form.pm[0] < form.pm[1]);

  return (
    <Card className="mb-6">
      <CardHeader
        title="Sedes con tópico"
        description="Cree una sede nueva cuando se habilite un tópico; luego configure sus consultorios, médicos y horario en las pestañas de abajo."
        icon={<Building2 className="size-[18px]" />}
        actions={
          <Button size="sm" icon={<Plus className="size-4" />} onClick={() => setForm(initialForm())}>
            Nueva sede
          </Button>
        }
      />
      {isLoading ? (
        <Skeleton className="m-5 h-16" />
      ) : (
        <ul className="divide-y divide-line">
          {data?.map((s) => (
            <li key={s.id} className={cn("flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-3", !s.is_active && "opacity-60")}>
              <Badge tone="brand">{s.ticket_prefix}-001</Badge>
              <div className="min-w-0 flex-1">
                <p className="font-semibold text-ink">
                  {s.name} {!s.is_active && <Badge className="ml-1">Inactiva</Badge>}
                </p>
                <p className="text-[13px] text-ink-soft">
                  Código {s.code}
                  {s.address ? ` · ${s.address}` : ""}
                </p>
              </div>
              {s.is_active && (
                <a
                  href={`/pantalla/${s.code.toLowerCase()}`}
                  target="_blank"
                  rel="noopener"
                  className="inline-flex items-center gap-1.5 text-[13px] font-medium text-brand-700 hover:underline"
                >
                  <MonitorPlay className="size-4" aria-hidden /> Pantalla
                </a>
              )}
              <Button size="sm" variant="ghost" loading={toggle.isPending && toggle.variables?.id === s.id} onClick={() => toggle.mutate(s)}>
                {s.is_active ? "Desactivar" : "Activar"}
              </Button>
            </li>
          ))}
        </ul>
      )}

      <Modal
        open={form !== null}
        onOpenChange={(open) => !open && setForm(null)}
        dismissable={false}
        size="lg"
        title="Nueva sede"
        description="Datos de la sede, configuración inicial y horario de atención del tópico. Todo podrá ajustarse después."
        footer={
          <>
            <Button variant="secondary" onClick={() => setForm(null)}>
              Cancelar
            </Button>
            <Button onClick={() => form && create.mutate(form)} loading={create.isPending} disabled={!valid}>
              Crear sede
            </Button>
          </>
        }
      >
        {form && (
          <div className="space-y-6">
            <section className="grid gap-4 sm:grid-cols-2">
              <Field label="Nombre" required className="sm:col-span-2">
                <Input value={form.name} maxLength={120} placeholder="Sede San Juan de Lurigancho" onChange={(e) => set({ name: e.target.value })} autoFocus />
              </Field>
              <Field label="Nombre corto" required hint="Se muestra en el selector de sede.">
                <Input value={form.short_name} maxLength={40} onChange={(e) => set({ short_name: e.target.value })} />
              </Field>
              <Field label="Código" required hint="Solo letras (2 a 10). Dirección de la pantalla: /pantalla/código.">
                <Input value={form.code} maxLength={10} onChange={(e) => set({ code: e.target.value.toUpperCase().replace(/[^A-Z]/g, "") })} />
              </Field>
              <Field label="Prefijo de turnos" required hint="1 a 3 letras, distinto al de otras sedes (A, B, …).">
                <Input value={form.ticket_prefix} maxLength={3} onChange={(e) => set({ ticket_prefix: e.target.value.toUpperCase().replace(/[^A-Z]/g, "") })} />
              </Field>
              <Field label="Inicio de atención">
                <Input type="date" min={todayIso()} value={form.valid_from} onChange={(e) => set({ valid_from: e.target.value })} />
              </Field>
              <Field label="Dirección">
                <Input value={form.address} maxLength={250} onChange={(e) => set({ address: e.target.value })} />
              </Field>
              <Field label="Ubicación del tópico" hint="Se incluye en los correos.">
                <Input value={form.location_note} maxLength={250} onChange={(e) => set({ location_note: e.target.value })} />
              </Field>
            </section>

            <section className="grid gap-4 border-t border-line pt-5 sm:grid-cols-3">
              <Field label="Capacidad diaria">
                <Input type="number" min={1} max={500} value={form.daily_capacity} onChange={(e) => set({ daily_capacity: Number(e.target.value) || 1 })} />
              </Field>
              <Field label="Minutos por atención">
                <Input type="number" min={5} max={120} value={form.slot_minutes} onChange={(e) => set({ slot_minutes: Number(e.target.value) || 5 })} />
              </Field>
              <Field label="Tolerancia (min)">
                <Input type="number" min={0} max={120} value={form.tolerance_minutes} onChange={(e) => set({ tolerance_minutes: Number(e.target.value) || 0 })} />
              </Field>
            </section>

            <section className="space-y-4 border-t border-line pt-5">
              <p className="text-[13px] font-medium text-ink">Días de atención</p>
              <div className="flex flex-wrap gap-2" role="group" aria-label="Días de atención">
                {DAYS.map((d, i) => (
                  <button
                    key={d}
                    type="button"
                    aria-pressed={form.days[i]}
                    onClick={() => set({ days: form.days.map((v, j) => (j === i ? !v : v)) })}
                    className={cn(
                      "rounded-lg px-3 py-1.5 text-sm font-medium ring-1 transition",
                      form.days[i] ? "bg-brand-700 text-white ring-brand-700" : "bg-panel text-ink-muted ring-line hover:ring-line-strong",
                    )}
                  >
                    {d}
                  </button>
                ))}
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Mañana: desde / hasta">
                  <div className="flex gap-2">
                    <Input type="time" value={form.am[0]} onChange={(e) => set({ am: [e.target.value, form.am[1]] })} />
                    <Input type="time" value={form.am[1]} onChange={(e) => set({ am: [form.am[0], e.target.value] })} />
                  </div>
                </Field>
                <div className="space-y-2">
                  <Toggle checked={form.pm_enabled} onChange={(v) => set({ pm_enabled: v })} label="Atiende por la tarde" />
                  {form.pm_enabled && (
                    <div className="flex gap-2">
                      <Input type="time" aria-label="Tarde desde" value={form.pm[0]} onChange={(e) => set({ pm: [e.target.value, form.pm[1]] })} />
                      <Input type="time" aria-label="Tarde hasta" value={form.pm[1]} onChange={(e) => set({ pm: [form.pm[0], e.target.value] })} />
                    </div>
                  )}
                </div>
              </div>
            </section>
          </div>
        )}
      </Modal>
    </Card>
  );
}
