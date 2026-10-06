import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CalendarX2, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { keys } from "@/features/appointments/api";
import { api } from "@/shared/api/client";
import type { Doctor, DoctorBlock } from "@/shared/api/types";
import { cn } from "@/shared/lib/cn";
import { fmt, todayIso } from "@/shared/lib/format";
import { notify } from "@/shared/lib/notify";
import { Badge, Button, Field, Input, Modal, Toggle } from "@/shared/ui";

const DAYS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];
const SHORT = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"];

const hhmm = (t: string) => t.slice(0, 5);

/** «lun–mié 08:00–12:00 · jue 14:00–17:00» (agrupa días consecutivos con el mismo horario). */
export function scheduleSummary(blocks: DoctorBlock[]): string {
  if (!blocks.length) return "Todo el horario de la sede";
  const byRange = new Map<string, number[]>();
  for (const b of blocks) {
    const key = `${hhmm(b.start_time)}–${hhmm(b.end_time)}`;
    byRange.set(key, [...(byRange.get(key) ?? []), b.weekday]);
  }
  return [...byRange.entries()]
    .map(([range, days]) => {
      const sorted = [...new Set(days)].sort();
      const groups: string[] = [];
      let start = sorted[0]!;
      let prev = start;
      for (const d of [...sorted.slice(1), Infinity]) {
        if (d !== prev + 1) {
          groups.push(start === prev ? SHORT[start - 1]! : `${SHORT[start - 1]}–${SHORT[prev - 1]}`);
          start = d;
        }
        prev = d;
      }
      return `${groups.join(", ")} ${range}`;
    })
    .join(" · ");
}

/** Estado del médico hoy (para la lista). */
export function DoctorTodayBadge({ doctor }: { doctor: Doctor }) {
  if (!doctor.is_active) return null;
  if (doctor.absence_reason) return <Badge tone="warning">Ausente hoy · {doctor.absence_reason}</Badge>;
  if (!doctor.present_today) return <Badge>No atiende hoy</Badge>;
  return doctor.on_duty_now ? <Badge tone="success">De turno</Badge> : <Badge tone="info">Atiende hoy</Badge>;
}

type Row = { enabled: boolean; start: string; end: string };

function toRows(blocks: DoctorBlock[]): Row[] {
  return DAYS.map((_, i) => {
    const b = blocks.find((x) => x.weekday === i + 1);
    return b ? { enabled: true, start: hhmm(b.start_time), end: hhmm(b.end_time) } : { enabled: false, start: "08:00", end: "12:00" };
  });
}

function useInvalidateDoctors(siteId: number) {
  const queryClient = useQueryClient();
  return () => {
    void queryClient.invalidateQueries({ queryKey: keys.doctors(siteId) });
    void queryClient.invalidateQueries({ queryKey: ["availability"] });
  };
}

/** Horario semanal del médico (un bloque por día). Sin horario = disponible en todo el horario de la sede. */
export function DoctorScheduleModal({ siteId, doctor, onClose }: { siteId: number; doctor: Doctor; onClose: () => void }) {
  const invalidate = useInvalidateDoctors(siteId);
  const [restricted, setRestricted] = useState(doctor.schedule.length > 0);
  const [rows, setRows] = useState<Row[]>(() => toRows(doctor.schedule));
  const multiBlock = new Set(doctor.schedule.map((b) => b.weekday)).size !== doctor.schedule.length;

  const save = useMutation({
    mutationFn: () =>
      api.put<Doctor>(`/sites/${siteId}/doctors/${doctor.id}/schedule`, {
        blocks: restricted
          ? rows.flatMap((r, i) => (r.enabled ? [{ weekday: i + 1, start_time: r.start, end_time: r.end }] : []))
          : [],
      }),
    onSuccess: () => {
      notify.success("Horario guardado", "La capacidad de los próximos días se recalculó según los médicos presentes.");
      invalidate();
      onClose();
    },
    onError: (e) => notify.error(e),
  });
  const valid = !restricted || (rows.some((r) => r.enabled) && rows.every((r) => !r.enabled || r.start < r.end));
  const set = (i: number, patch: Partial<Row>) => setRows(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));

  return (
    <Modal
      open
      onOpenChange={(open) => !open && onClose()}
      dismissable={false}
      title={`Horario de ${doctor.full_name}`}
      description="Define qué días y en qué horas atiende. Al iniciar una atención, la mesa ofrece primero a los médicos de turno."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button onClick={() => save.mutate()} loading={save.isPending} disabled={!valid}>
            Guardar horario
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Toggle
          checked={restricted}
          onChange={setRestricted}
          label="Tiene horario propio"
          description="Si está desactivado, se considera disponible durante todo el horario de atención de la sede."
        />
        {multiBlock && (
          <p className="text-[0.8125rem] text-warning">Este médico tenía varios bloques en un mismo día; al guardar se conserva uno por día.</p>
        )}
        {restricted && (
          <ul className="divide-y divide-line rounded-xl border border-line">
            {rows.map((r, i) => (
              <li key={DAYS[i]} className="flex flex-wrap items-center gap-3 px-4 py-2.5">
                <label className="flex w-32 items-center gap-2 text-sm font-medium">
                  <input type="checkbox" className="size-4 accent-brand-700" checked={r.enabled} onChange={(e) => set(i, { enabled: e.target.checked })} />
                  {DAYS[i]}
                </label>
                <div className={cn("flex items-center gap-2", !r.enabled && "opacity-40")}>
                  <Input type="time" aria-label={`${DAYS[i]} desde`} disabled={!r.enabled} value={r.start} onChange={(e) => set(i, { start: e.target.value })} className="w-32" />
                  <span className="text-ink-soft">a</span>
                  <Input type="time" aria-label={`${DAYS[i]} hasta`} disabled={!r.enabled} value={r.end} onChange={(e) => set(i, { end: e.target.value })} className="w-32" />
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Modal>
  );
}

/** Ausencias del médico (vacaciones, licencia, capacitación): reducen la capacidad calculada de esos días. */
export function DoctorAbsencesModal({ siteId, doctor, onClose }: { siteId: number; doctor: Doctor; onClose: () => void }) {
  const invalidate = useInvalidateDoctors(siteId);
  const [form, setForm] = useState({ date_from: todayIso(), date_to: todayIso(), reason: "" });
  const add = useMutation({
    mutationFn: () => api.post<Doctor>(`/sites/${siteId}/doctors/${doctor.id}/absences`, form),
    onSuccess: () => {
      notify.success("Ausencia registrada");
      setForm({ ...form, reason: "" });
      invalidate();
    },
    onError: (e) => notify.error(e),
  });
  const remove = useMutation({
    mutationFn: (id: number) => api.delete<Doctor>(`/sites/${siteId}/doctors/${doctor.id}/absences/${id}`),
    onSuccess: () => (notify.success("Ausencia eliminada"), invalidate()),
    onError: (e) => notify.error(e),
  });

  return (
    <Modal open onOpenChange={(open) => !open && onClose()} title={`Ausencias de ${doctor.full_name}`} description="Solo el motivo administrativo (sin datos de salud).">
      <div className="space-y-5">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Desde">
            <Input type="date" min={todayIso()} value={form.date_from} onChange={(e) => setForm({ ...form, date_from: e.target.value, date_to: form.date_to < e.target.value ? e.target.value : form.date_to })} />
          </Field>
          <Field label="Hasta">
            <Input type="date" min={form.date_from} value={form.date_to} onChange={(e) => setForm({ ...form, date_to: e.target.value })} />
          </Field>
          <Field label="Motivo" className="sm:col-span-2">
            <Input value={form.reason} maxLength={150} placeholder="Vacaciones, licencia, capacitación…" onChange={(e) => setForm({ ...form, reason: e.target.value })} />
          </Field>
        </div>
        <Button onClick={() => add.mutate()} loading={add.isPending} disabled={form.reason.trim().length < 3} icon={<Plus className="size-4" />}>
          Registrar ausencia
        </Button>
        <div>
          <p className="mb-2 text-[0.8125rem] font-medium text-ink">Próximas ausencias</p>
          {doctor.upcoming_absences.length === 0 ? (
            <p className="text-sm text-ink-soft">Sin ausencias registradas.</p>
          ) : (
            <ul className="divide-y divide-line rounded-xl border border-line">
              {doctor.upcoming_absences.map((a) => (
                <li key={a.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
                  <CalendarX2 className="size-4 text-ink-soft" aria-hidden />
                  <span className="tabular font-medium">
                    {fmt.date(a.date_from)}
                    {a.date_to !== a.date_from && ` – ${fmt.date(a.date_to)}`}
                  </span>
                  <span className="flex-1 text-ink-muted">{a.reason}</span>
                  <Button size="sm" variant="ghost" icon={<Trash2 className="size-4" />} loading={remove.isPending && remove.variables === a.id} onClick={() => remove.mutate(a.id)}>
                    Quitar
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </Modal>
  );
}


