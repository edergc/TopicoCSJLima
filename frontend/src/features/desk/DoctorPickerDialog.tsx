import { Stethoscope } from "lucide-react";
import { useState } from "react";

import type { Appointment, Doctor } from "@/shared/api/types";
import { cn } from "@/shared/lib/cn";
import { Button, Modal } from "@/shared/ui";

/** Al iniciar una atención en una sede con varios médicos activos: ¿quién atiende? */
export function DoctorPickerDialog({
  appointment,
  doctors,
  loading,
  onClose,
  onConfirm,
}: {
  appointment: Appointment;
  doctors: Doctor[];
  loading: boolean;
  onClose: () => void;
  onConfirm: (doctorId: number) => void;
}) {
  const [selected, setSelected] = useState<number | null>(null);
  return (
    <Modal
      open
      onOpenChange={(open) => !open && onClose()}
      size="sm"
      title={`Iniciar atención ${appointment.ticket_code}`}
      description={`${appointment.worker.display_name} · Seleccione el médico que atiende.`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button onClick={() => selected !== null && onConfirm(selected)} disabled={selected === null} loading={loading}>
            Iniciar atención
          </Button>
        </>
      }
    >
      <div role="radiogroup" aria-label="Médico" className="grid gap-2">
        {doctors.map((d) => (
          <button
            key={d.id}
            type="button"
            role="radio"
            aria-checked={selected === d.id}
            onClick={() => setSelected(d.id)}
            onDoubleClick={() => onConfirm(d.id)}
            className={cn(
              "flex items-center gap-3 rounded-xl border px-4 py-3 text-left transition",
              selected === d.id ? "border-brand-600 bg-brand-50 ring-1 ring-brand-600" : "border-line hover:border-line-strong hover:bg-sunken/50",
            )}
          >
            <span className="grid size-9 place-items-center rounded-full bg-status-inservice-bg text-status-inservice">
              <Stethoscope className="size-4" aria-hidden />
            </span>
            <span className="min-w-0">
              <span className="flex items-center gap-2 font-semibold text-ink">
                {d.full_name}
                {d.on_duty_now && <span className="rounded-full bg-status-done-bg px-2 py-0.5 text-[11px] font-semibold text-status-done">De turno</span>}
              </span>
              <span className="block text-[13px] text-ink-soft">{[d.specialty, d.cmp && `CMP ${d.cmp}`].filter(Boolean).join(" · ") || "—"}</span>
            </span>
          </button>
        ))}
      </div>
    </Modal>
  );
}
