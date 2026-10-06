import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Coffee, Lock, MonitorPlay, Stethoscope, Timer, Users } from "lucide-react";

import { api } from "@/shared/api/client";
import type { LiveBoard, LiveSite } from "@/shared/api/types";
import { useSite } from "@/shared/auth/SiteProvider";
import { cn } from "@/shared/lib/cn";
import { fmt, minutesSince, formatDuration } from "@/shared/lib/format";
import { useDocumentTitle, useNow } from "@/shared/lib/hooks";
import { syncServerTime } from "@/shared/lib/serverTime";
import { Badge, Card, EmptyState, PageHeader, Skeleton } from "@/shared/ui";
import { useNavigate } from "react-router-dom";

const REFRESH_MS = 10_000;
const LONG_WAIT_MINUTES = 45;

/** Panel en vivo: todas las sedes del usuario a la vez (para la supervisión). */
export default function LivePanelPage() {
  useDocumentTitle("Panel en vivo");
  const { data, isLoading } = useQuery({
    queryKey: ["live-board"],
    queryFn: async () => {
      const sentAt = Date.now();
      const board = await api.get<LiveBoard>("/dashboard/live");
      syncServerTime(board.generated_at, (sentAt + Date.now()) / 2);
      return board;
    },
    refetchInterval: REFRESH_MS,
  });

  return (
    <div>
      <PageHeader
        eyebrow="Operación"
        title="Panel en vivo"
        description={
          <>
            Estado de todas sus sedes en tiempo real (se actualiza cada 10 s).
            {data && <span className="text-ink-soft"> Actualizado a las {fmt.time(data.generated_at)}.</span>}
          </>
        }
      />
      {isLoading ? (
        <div className="grid gap-5 xl:grid-cols-2">
          <Skeleton className="h-72 rounded-[var(--radius-card)]" />
          <Skeleton className="h-72 rounded-[var(--radius-card)]" />
        </div>
      ) : !data?.sites.length ? (
        <EmptyState icon={MonitorPlay} title="Sin sedes asignadas" />
      ) : (
        <div className="grid gap-5 xl:grid-cols-2">
          {data.sites.map((s) => (
            <SiteCard key={s.site_id} site={s} />
          ))}
        </div>
      )}
    </div>
  );
}

function SiteCard({ site }: { site: LiveSite }) {
  const now = useNow(30_000);
  const navigate = useNavigate();
  const { setSiteId } = useSite();
  const c = site.counts;
  const longWait = (site.longest_wait_minutes ?? 0) >= LONG_WAIT_MINUTES;
  const closed = site.day_status === "CLOSED";
  const openDesk = () => {
    setSiteId(site.site_id);
    navigate("/mesa");
  };

  return (
    <Card className={cn("overflow-hidden", site.incidents.length > 0 && "ring-1 ring-warning/40")}>
      <div className="flex flex-wrap items-center gap-3 border-b border-line px-5 py-4">
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-lg font-semibold tracking-tight">{site.site_name}</h2>
          <p className="text-[13px] text-ink-soft">
            {closed ? "Jornada cerrada" : site.day_status ? "Jornada abierta" : "Sin turnos registrados hoy"}
            {site.next_ticket_code && ` · siguiente: ${site.next_ticket_code}`}
          </p>
        </div>
        {site.pause && (
          <Badge tone="warning">
            <Coffee className="mr-1 inline size-3.5" aria-hidden />
            Pausa hasta {fmt.time(site.pause.resume_at)}
          </Badge>
        )}
        {closed && (
          <Badge>
            <Lock className="mr-1 inline size-3.5" aria-hidden />
            Cerrado
          </Badge>
        )}
        <button type="button" onClick={openDesk} className="text-[13px] font-medium text-brand-700 hover:underline">
          Ir a la mesa
        </button>
      </div>

      <dl className="grid grid-cols-2 gap-px bg-line sm:grid-cols-4">
        <Stat label="En espera" value={c.waiting + c.called} />
        <Stat label="En atención" value={c.in_service} />
        <Stat label="Atendidos" value={c.attended} />
        <Stat label="Cupos libres" value={c.available} hint={`de ${c.capacity}`} tone={c.available === 0 && c.capacity > 0 ? "danger" : undefined} />
      </dl>

      <div className="grid gap-4 p-5 sm:grid-cols-2">
        <div className="space-y-2 text-sm">
          <p className="flex items-center gap-2">
            <Timer className="size-4 text-ink-soft" aria-hidden />
            Mayor espera actual:{" "}
            <b className={cn("tabular", longWait && "text-danger")}>
              {site.longest_wait_minutes !== null ? formatDuration(site.longest_wait_minutes) : "—"}
            </b>
          </p>
          <p className="flex items-center gap-2">
            <Users className="size-4 text-ink-soft" aria-hidden />
            Espera promedio hoy: <b className="tabular">{site.avg_wait_minutes !== null ? `${fmt.number(site.avg_wait_minutes)} min` : "—"}</b>
          </p>
          <p className="text-ink-soft">
            No presentados {c.no_show} · cancelados {c.cancelled}
          </p>
        </div>
        <div>
          <p className="mb-1.5 text-[13px] font-medium text-ink-muted">En atención</p>
          {site.in_service.length === 0 ? (
            <p className="text-sm text-ink-soft">Nadie en atención.</p>
          ) : (
            <ul className="space-y-1.5">
              {site.in_service.map((s) => (
                <li key={s.ticket_code} className="flex items-center gap-2 text-sm">
                  <Stethoscope className="size-4 text-status-inservice" aria-hidden />
                  <b className="tabular whitespace-nowrap">{s.ticket_code}</b>
                  <span className="min-w-0 flex-1 truncate text-ink-muted">{[s.doctor_name, s.room_name].filter(Boolean).join(" · ") || "—"}</span>
                  <span className="tabular whitespace-nowrap text-ink-soft">{formatDuration(minutesSince(s.started_at, now))}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {site.incidents.length > 0 && (
        <ul className="space-y-1 border-t border-line bg-status-waiting-bg/50 px-5 py-3">
          {site.incidents.map((i) => (
            <li key={`${i.code}-${i.message}`} className="flex items-start gap-2 text-[13px] text-status-waiting">
              <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden /> {i.message}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function Stat({ label, value, hint, tone }: { label: string; value: number; hint?: string; tone?: "danger" }) {
  return (
    <div className="bg-panel px-5 py-3">
      <dt className="text-xs font-medium tracking-wide text-ink-soft uppercase">{label}</dt>
      <dd className={cn("tabular text-2xl font-semibold", tone === "danger" && "text-danger")}>
        {value}
        {hint && <span className="ml-1 text-sm font-normal text-ink-soft">{hint}</span>}
      </dd>
    </div>
  );
}
