import { useMutation, useQueryClient } from "@tanstack/react-query";
import { HeartHandshake } from "lucide-react";
import { useState } from "react";

import { useReasons } from "@/features/appointments/api";
import { api } from "@/shared/api/client";
import type { Appointment } from "@/shared/api/types";
import { cn } from "@/shared/lib/cn";
import { notify } from "@/shared/lib/notify";
import { Badge, Button, Modal } from "@/shared/ui";

/** Distintivo de atención prioritaria (solo en la mesa: la pantalla de sala no muestra la categoría). */
export function PriorityBadge({ appointment }: { appointment: Appointment }) {
  if (!appointment.priority_label) return null;
  return (
    <Badge tone="info" className="whitespace-nowrap">
      <HeartHandshake className="mr-1 inline size-3.5" aria-hidden />
      <span title={appointment.priority_label}>Prioritaria</span>
    </Badge>
  );
}

/** Selector de categoría de prioridad para el registro. */
export function PrioritySelect({ value, onChange }: { value: number | null; onChange: (id: number | null) => void }) {
  const { data: reasons } = useReasons("PRIORITY");
  return (
    <div className="space-y-2">
      <p className="flex items-center gap-1.5 text-[0.8125rem] font-medium">
        <HeartHandshake className="size-4 text-status-called" aria-hidden /> Atención prioritaria
      </p>
      <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Atención prioritaria">
        {[{ id: null, label: "No" }, ...(reasons ?? []).map((r) => ({ id: r.id as number | null, label: r.label }))].map((o) => (
          <button
            key={o.id ?? "none"}
            type="button"
            role="radio"
            aria-checked={value === o.id}
            onClick={() => onChange(o.id)}
            className={cn(
              "rounded-lg px-3 py-1.5 text-[0.8125rem] ring-1 transition",
              value === o.id ? "bg-brand-700 font-medium text-white ring-brand-700" : "bg-panel text-ink-muted ring-line hover:ring-line-strong",
            )}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  );
}

/** Asignar o retirar la prioridad de quien espera (queda en la línea de tiempo y en la auditoría). */
export function PriorityDialog({ appointment, onClose }: { appointment: Appointment; onClose: () => void }) {
  const queryClient = useQueryClient();
  const { data: reasons } = useReasons("PRIORITY");
  const current = reasons?.find((r) => r.code === appointment.priority_code)?.id ?? null;
  const [selected, setSelected] = useState<number | null>(current);
  const save = useMutation({
    mutationFn: () => api.post<Appointment>(`/appointments/${appointment.public_id}/priority`, { reason_id: selected }),
    onSuccess: (a) => {
      notify.success(a.priority_label ? `Turno ${a.ticket_code}: atención prioritaria` : `Turno ${a.ticket_code}: orden normal`);
      void queryClient.invalidateQueries({ queryKey: ["queue"] });
      onClose();
    },
    onError: (e) => notify.error(e),
  });
  return (
    <Modal
      open
      onOpenChange={(o) => !o && onClose()}
      size="sm"
      title={`Prioridad del turno ${appointment.ticket_code}`}
      description="Las atenciones prioritarias se llaman antes, respetando el tope de llamados prioritarios seguidos. Queda registrado en la auditoría."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button onClick={() => save.mutate()} loading={save.isPending} disabled={selected === current}>
            Guardar
          </Button>
        </>
      }
    >
      <PrioritySelect value={selected} onChange={setSelected} />
    </Modal>
  );
}
