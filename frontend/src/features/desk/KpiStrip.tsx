import { BellRing, CheckCircle2, CircleSlash, Hourglass, LayoutGrid, Ticket } from "lucide-react";

import type { QueueCounts } from "@/shared/api/types";
import { KpiCard, Skeleton } from "@/shared/ui";

/** Indicadores que responden de inmediato: ¿cuántos cupos quedan?, ¿cuántos esperan?, ¿cuántos atendidos? */
export function KpiStrip({ counts }: { counts: QueueCounts | undefined }) {
  if (!counts) {
    return (
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} className="h-[74px] rounded-[var(--radius-card)]" />
        ))}
      </div>
    );
  }
  const closed = counts.cancelled + counts.no_show;
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
      <KpiCard
        label="Disponibles"
        value={counts.available}
        icon={Ticket}
        tone={counts.available === 0 ? "danger" : "brand"}
        hint={`de ${counts.capacity} cupos`}
        emphasis
      />
      <KpiCard label="Registrados" value={counts.total - counts.voided} icon={LayoutGrid} hint={`${counts.occupied} ocupan cupo`} />
      <KpiCard label="En espera" value={counts.waiting} icon={Hourglass} tone="waiting" hint="en la cola" />
      <KpiCard
        label="En curso"
        value={counts.called + counts.in_service}
        icon={BellRing}
        tone="called"
        hint={`${counts.called} llamado · ${counts.in_service} en atención`}
      />
      <KpiCard label="Atendidos" value={counts.attended} icon={CheckCircle2} tone="done" hint="finalizados" />
      <KpiCard
        label="Cerrados"
        value={closed}
        icon={CircleSlash}
        tone={closed > 0 ? "danger" : "neutral"}
        hint={`${counts.cancelled} cancel. · ${counts.no_show} no pres.`}
      />
    </div>
  );
}
