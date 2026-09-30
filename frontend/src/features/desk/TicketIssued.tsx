import { CheckCircle2, X } from "lucide-react";

import type { Appointment } from "@/shared/api/types";
import { fmt } from "@/shared/lib/format";
import { IconButton } from "@/shared/ui";

/** Confirmación prominente del turno generado: la encargada lo dicta por teléfono. */
export function TicketIssued({ appointment, onDismiss }: { appointment: Appointment; onDismiss: () => void }) {
  return (
    <div
      role="status"
      aria-live="assertive"
      className="relative animate-slide-up overflow-hidden rounded-[var(--radius-card)] bg-brand-800 p-5 text-white shadow-[var(--shadow-raised)]"
    >
      <div className="absolute -top-16 -right-16 size-48 rounded-full bg-white/6" aria-hidden />
      <IconButton
        label="Cerrar confirmación"
        size="sm"
        onClick={onDismiss}
        className="absolute top-3 right-3 text-white/70 hover:bg-white/10 hover:text-white"
        icon={<X className="size-4" />}
      />
      <p className="flex items-center gap-2 text-sm font-medium text-white/80">
        <CheckCircle2 className="size-4" aria-hidden /> Turno registrado
      </p>
      <p className="tabular mt-1 text-6xl leading-none font-bold tracking-tight">{appointment.ticket_code}</p>
      <p className="mt-3 truncate text-[15px] font-medium">{appointment.worker.display_name}</p>
      <dl className="mt-4 grid grid-cols-3 gap-3 border-t border-white/15 pt-4 text-sm">
        <div>
          <dt className="text-xs text-white/60">Posición</dt>
          <dd className="tabular text-lg font-semibold">{appointment.position ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-xs text-white/60">Personas delante</dt>
          <dd className="tabular text-lg font-semibold">{appointment.people_ahead ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-xs text-white/60">Hora estimada</dt>
          <dd className="tabular text-lg font-semibold">{appointment.estimated_at ? fmt.time(appointment.estimated_at) : "—"}</dd>
        </div>
      </dl>
      <p className="mt-3 text-xs text-white/60">La hora estimada es referencial y se recalcula conforme avanza la cola.</p>
    </div>
  );
}
