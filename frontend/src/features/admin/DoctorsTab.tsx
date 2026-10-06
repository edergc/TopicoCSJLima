import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, CalendarX2, Pencil, Plus, Stethoscope } from "lucide-react";
import { useState } from "react";

import { keys, useDoctors } from "@/features/appointments/api";
import { api } from "@/shared/api/client";
import type { Doctor } from "@/shared/api/types";
import { useAuth } from "@/shared/auth/AuthProvider";
import { notify } from "@/shared/lib/notify";
import { Badge, Button, Card, CardHeader, EmptyState, Field, Input, Modal, Skeleton, Toggle } from "@/shared/ui";

import { DoctorAbsencesModal, DoctorScheduleModal, DoctorTodayBadge, scheduleSummary } from "./DoctorAvailability";

type Form = { full_name: string; document_number: string; cmp: string; specialty: string; phone: string; email: string; is_active: boolean };

const EMPTY: Form = { full_name: "", document_number: "", cmp: "", specialty: "Medicina General", phone: "", email: "", is_active: true };

function toForm(d: Doctor): Form {
  return {
    full_name: d.full_name,
    document_number: d.document_number ?? "",
    cmp: d.cmp ?? "",
    specialty: d.specialty ?? "",
    phone: d.phone ?? "",
    email: d.email ?? "",
    is_active: d.is_active,
  };
}

/** Médicos del tópico de la sede: se asignan a cada atención al iniciarla (para reportes y la pantalla de sala). */
export function DoctorsTab({ siteId }: { siteId: number }) {
  const { can } = useAuth();
  const queryClient = useQueryClient();
  const { data, isLoading } = useDoctors(siteId);
  const [editing, setEditing] = useState<{ doctor: Doctor | null; form: Form } | null>(null);
  const [scheduleFor, setScheduleFor] = useState<Doctor | null>(null);
  const [absencesFor, setAbsencesFor] = useState<Doctor | null>(null);
  const canEdit = can("site:configure");

  const save = useMutation({
    mutationFn: ({ doctor, form }: { doctor: Doctor | null; form: Form }) => {
      const body = {
        full_name: form.full_name.trim(),
        document_number: form.document_number || null,
        cmp: form.cmp || null,
        specialty: form.specialty.trim() || null,
        phone: form.phone.trim() || null,
        email: form.email.trim() || null,
      };
      return doctor
        ? api.patch<Doctor>(`/sites/${siteId}/doctors/${doctor.id}`, { ...body, is_active: form.is_active })
        : api.post<Doctor>(`/sites/${siteId}/doctors`, body);
    },
    onSuccess: (_d, vars) => {
      notify.success(vars.doctor ? "Médico actualizado" : "Médico registrado");
      setEditing(null);
      void queryClient.invalidateQueries({ queryKey: keys.doctors(siteId) });
    },
    onError: (e) => notify.error(e),
  });

  const form = editing?.form;
  const set = (patch: Partial<Form>) => editing && setEditing({ ...editing, form: { ...editing.form, ...patch } });
  const valid =
    form !== undefined &&
    form.full_name.trim().length >= 3 &&
    (form.document_number === "" || /^\d{8}$/.test(form.document_number)) &&
    (form.cmp === "" || /^\d{1,6}$/.test(form.cmp));

  return (
    <Card>
      <CardHeader
        title="Médicos del tópico"
        description="Al iniciar cada atención se registra qué médico atendió; se ofrece primero a los médicos de turno. Con horarios definidos, la capacidad del día se calcula con los médicos presentes."
        icon={<Stethoscope className="size-[18px]" />}
        actions={
          canEdit && (
            <Button size="sm" icon={<Plus className="size-4" />} onClick={() => setEditing({ doctor: null, form: EMPTY })}>
              Registrar médico
            </Button>
          )
        }
      />
      {isLoading ? (
        <Skeleton className="m-5 h-24" />
      ) : !data?.length ? (
        <EmptyState icon={Stethoscope} title="Aún no hay médicos registrados" description="Registre a los médicos que atienden en el tópico de esta sede." />
      ) : (
        <ul>
          {data.map((d) => (
            <li key={d.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-line px-5 py-3 last:border-b-0">
              <span className="grid size-9 place-items-center rounded-full bg-brand-50 text-brand-700">
                <Stethoscope className="size-4" aria-hidden />
              </span>
              <div className="min-w-0 flex-1">
                <p className="flex flex-wrap items-center gap-2 font-semibold text-ink">
                  {d.full_name} {!d.is_active && <Badge>Inactivo</Badge>}
                  <DoctorTodayBadge doctor={d} />
                </p>
                <p className="text-[0.8125rem] text-ink-soft">
                  {[d.specialty, d.cmp && `CMP ${d.cmp}`, d.document_number && `DNI ${d.document_number}`, d.phone].filter(Boolean).join(" · ") || "—"}
                </p>
                <p className="text-[0.8125rem] text-ink-muted">
                  <CalendarClock className="mr-1 inline size-3.5" aria-hidden />
                  {scheduleSummary(d.schedule)}
                  {d.upcoming_absences.length > 0 && ` · ${d.upcoming_absences.length} ausencia(s) programada(s)`}
                </p>
              </div>
              {canEdit && (
                <div className="flex flex-wrap gap-1">
                  <Button size="sm" variant="ghost" icon={<CalendarClock className="size-4" />} onClick={() => setScheduleFor(d)}>
                    Horario
                  </Button>
                  <Button size="sm" variant="ghost" icon={<CalendarX2 className="size-4" />} onClick={() => setAbsencesFor(d)}>
                    Ausencias
                  </Button>
                  <Button size="sm" variant="ghost" icon={<Pencil className="size-4" />} onClick={() => setEditing({ doctor: d, form: toForm(d) })}>
                    Editar
                  </Button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {scheduleFor && <DoctorScheduleModal siteId={siteId} doctor={scheduleFor} onClose={() => setScheduleFor(null)} />}
      {absencesFor && (
        <DoctorAbsencesModal
          siteId={siteId}
          doctor={data?.find((d) => d.id === absencesFor.id) ?? absencesFor}
          onClose={() => setAbsencesFor(null)}
        />
      )}
      <Modal
        open={editing !== null}
        onOpenChange={(open) => !open && setEditing(null)}
        dismissable={false}
        title={editing?.doctor ? "Editar médico" : "Registrar médico"}
        description="Solo datos administrativos del profesional."
        footer={
          <>
            <Button variant="secondary" onClick={() => setEditing(null)}>
              Cancelar
            </Button>
            <Button onClick={() => editing && save.mutate(editing)} loading={save.isPending} disabled={!valid}>
              Guardar
            </Button>
          </>
        }
      >
        {form && (
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Nombre completo" required className="sm:col-span-2" hint="Como se mostrará, p. ej. «Dra. Ana Pérez Soto».">
              <Input value={form.full_name} maxLength={150} onChange={(e) => set({ full_name: e.target.value })} autoFocus />
            </Field>
            <Field label="CMP (colegiatura)">
              <Input inputMode="numeric" maxLength={6} value={form.cmp} onChange={(e) => set({ cmp: e.target.value.replace(/\D/g, "") })} />
            </Field>
            <Field label="DNI">
              <Input inputMode="numeric" maxLength={8} value={form.document_number} onChange={(e) => set({ document_number: e.target.value.replace(/\D/g, "") })} />
            </Field>
            <Field label="Especialidad">
              <Input value={form.specialty} maxLength={80} onChange={(e) => set({ specialty: e.target.value })} />
            </Field>
            <Field label="Teléfono">
              <Input value={form.phone} maxLength={20} onChange={(e) => set({ phone: e.target.value })} />
            </Field>
            <Field label="Correo" className="sm:col-span-2">
              <Input type="email" value={form.email} maxLength={150} onChange={(e) => set({ email: e.target.value })} />
            </Field>
            {editing?.doctor && (
              <div className="sm:col-span-2">
                <Toggle
                  checked={form.is_active}
                  onChange={(v) => set({ is_active: v })}
                  label="Activo"
                  description="Un médico inactivo no se puede asignar a nuevas atenciones (se conserva su historial)."
                />
              </div>
            )}
          </div>
        )}
      </Modal>
    </Card>
  );
}
