import { BellRing, DoorOpen, Stethoscope } from "lucide-react";

import type { RoomStatus } from "@/shared/api/types";
import { cn } from "@/shared/lib/cn";
import { formatDuration, minutesSince } from "@/shared/lib/format";
import { useNow } from "@/shared/lib/hooks";

const TONE = {
  FREE: { card: "border-status-done/30 bg-status-done-bg/60", dot: "bg-status-done", label: "Libre", Icon: DoorOpen },
  CALLED: { card: "border-status-called/30 bg-status-called-bg/70", dot: "bg-status-called", label: "Llamando", Icon: BellRing },
  IN_SERVICE: { card: "border-status-inservice/30 bg-status-inservice-bg/70", dot: "bg-status-inservice", label: "En atención", Icon: Stethoscope },
} as const;

interface Props {
  rooms: RoomStatus[];
  /** Consultorio al que irá el próximo llamado. */
  targetId: number | null;
  /** Elegir otro consultorio libre como destino del próximo llamado. */
  onTarget: (roomId: number) => void;
}

/**
 * Estado de los consultorios: la encargada ve de un vistazo cuál está libre y quién ocupa cada uno.
 * El próximo llamado va al consultorio marcado (por defecto, el primero libre); se puede elegir otro libre.
 */
export function RoomsPanel({ rooms, targetId, onTarget }: Props) {
  const now = useNow(15_000);
  return (
    <section aria-label="Consultorios" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {rooms.map((room) => {
        const tone = TONE[room.status];
        const free = room.status === "FREE";
        const target = free && room.id === targetId;
        const content = (
          <>
            <div className="flex items-center justify-between gap-2">
              <p className="flex items-center gap-2 text-sm font-bold tracking-wide text-ink uppercase">
                <tone.Icon className="size-4" aria-hidden /> {room.name}
              </p>
              <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-ink">
                <span className={cn("size-2.5 rounded-full", tone.dot, room.status === "CALLED" && "animate-pulse")} aria-hidden />
                {tone.label}
              </span>
            </div>
            {free ? (
              <p className={cn("mt-1 text-[0.8125rem]", target ? "font-semibold text-status-done" : "text-ink-soft")}>
                {target ? "El próximo llamado viene aquí" : "Pulse para llamar aquí"}
              </p>
            ) : (
              <>
                <p className="mt-1 truncate text-sm text-ink">
                  <span className="tabular font-bold">{room.ticket_code}</span> · {room.worker_name}
                </p>
                <p className="truncate text-[0.8125rem] text-ink-muted">
                  {room.doctor_name ? `${room.doctor_name} · ` : ""}
                  {formatDuration(minutesSince(room.since, now))}
                </p>
              </>
            )}
          </>
        );
        const base = cn("rounded-xl border p-3.5 text-left transition", tone.card, target && "ring-2 ring-status-done ring-offset-2 ring-offset-surface");
        return free ? (
          <button key={room.id} type="button" onClick={() => onTarget(room.id)} aria-pressed={target} className={cn(base, "hover:ring-2 hover:ring-status-done/60")}>
            {content}
          </button>
        ) : (
          <div key={room.id} className={base}>
            {content}
          </div>
        );
      })}
    </section>
  );
}
