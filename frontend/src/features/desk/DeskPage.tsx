import { AlertTriangle, CalendarX2, RefreshCw } from "lucide-react";
import { useRef, useState } from "react";

import { AppointmentDrawer } from "@/features/appointments/components/AppointmentDrawer";
import { ACTIONS_WITH_REASON, ReasonActionDialog } from "@/features/appointments/components/ReasonActionDialog";
import { useAvailability, useCallNext, useQueue, useTransition } from "@/features/appointments/api";
import type { Appointment, AppointmentAction } from "@/shared/api/types";
import { useAuth } from "@/shared/auth/AuthProvider";
import { useSite } from "@/shared/auth/SiteProvider";
import { cn } from "@/shared/lib/cn";
import { fmt } from "@/shared/lib/format";
import { useDocumentTitle, useHotkey } from "@/shared/lib/hooks";
import { errorMessage, notify } from "@/shared/lib/notify";
import { Button, Callout, Skeleton } from "@/shared/ui";

import { KpiStrip } from "./KpiStrip";
import { QueueBoard } from "./QueueBoard";
import { RegisterPanel, type RegisterPanelHandle } from "./RegisterPanel";
import { TicketIssued } from "./TicketIssued";

/**
 * Mesa de atención: la pantalla principal de la encargada del tópico.
 * Pensada para operar mientras atiende llamadas: pocos clics, atajos (F2 / F4),
 * estados visibles y confirmación para toda acción sensible.
 */
export default function DeskPage() {
  useDocumentTitle("Mesa de atención");
  const { site } = useSite();
  const { can } = useAuth();
  const siteId = site?.id;
  const queue = useQueue(siteId);
  const availability = useAvailability(siteId);
  const callNext = useCallNext(siteId);
  const transition = useTransition();
  const registerRef = useRef<RegisterPanelHandle>(null);

  const [issued, setIssued] = useState<Appointment | null>(null);
  const [dialog, setDialog] = useState<{ appointment: Appointment; action: AppointmentAction } | null>(null);
  const [detailId, setDetailId] = useState<string | null>(null);

  const canOperate = can("appointment:operate");

  const handleAction = (appointment: Appointment, action: AppointmentAction) => {
    if (ACTIONS_WITH_REASON.has(action)) {
      setDialog({ appointment, action });
      return;
    }
    transition.mutate(
      { appointment, action },
      {
        onSuccess: (updated) => {
          if (action === "CALL") notify.info(`Turno ${updated.ticket_code} llamado`, updated.worker.display_name);
          if (action === "FINISH") notify.success(`Atención ${updated.ticket_code} finalizada`);
        },
      },
    );
  };

  const handleCallNext = () => {
    if (!canOperate || callNext.isPending) return;
    callNext.mutate(undefined, {
      onSuccess: (a) => notify.info(`Turno ${a.ticket_code} llamado`, `${a.worker.display_name} — indíquele que se acerque al tópico.`),
      onError: (error) => notify.error(error),
    });
  };

  useHotkey("F2", () => registerRef.current?.focus());
  useHotkey("F4", handleCallNext, canOperate);

  if (!site) return <Callout tone="danger">Su usuario no tiene una sede asignada.</Callout>;

  const data = queue.data;
  const closedDay = availability.data && !availability.data.blocks.length;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-semibold tracking-[0.08em] text-brand-700 uppercase">Mesa de atención</p>
          <h1 className="text-2xl font-semibold tracking-tight">{site.name}</h1>
        </div>
        <div className="flex items-center gap-3 text-[13px] text-ink-soft">
          {availability.data?.blocks.map((b) => (
            <span key={b.block} className="tabular hidden rounded-lg bg-panel px-2.5 py-1 ring-1 ring-line md:inline">
              {b.block === "AM" ? "Mañana" : "Tarde"} {b.start.slice(0, 5)}–{b.end.slice(0, 5)}
            </span>
          ))}
          <span className={cn("inline-flex items-center gap-1.5", queue.isFetching && "text-brand-700")} aria-live="polite">
            <RefreshCw className={cn("size-3.5", queue.isFetching && "animate-spin")} aria-hidden />
            {data ? `Actualizado ${fmt.time(data.generated_at)}` : "Cargando…"}
          </span>
        </div>
      </div>

      {queue.isError && (
        <Callout
          tone="danger"
          title="No se pudo actualizar la cola"
          action={
            <Button size="sm" variant="secondary" onClick={() => void queue.refetch()}>
              Reintentar
            </Button>
          }
        >
          {errorMessage(queue.error)} Los datos mostrados pueden no estar al día.
        </Callout>
      )}

      <KpiStrip counts={data?.counts} />

      {data && data.incidents.length > 0 && (
        <div className="flex flex-wrap gap-2" role="status" aria-label="Incidencias">
          {data.incidents.map((incident, i) => (
            <span
              key={i}
              className="inline-flex items-center gap-1.5 rounded-lg bg-status-waiting-bg px-3 py-1.5 text-[13px] font-medium text-amber-900 ring-1 ring-status-waiting/25"
            >
              <AlertTriangle className="size-3.5" aria-hidden /> {incident.message}
            </span>
          ))}
        </div>
      )}

      {closedDay && (
        <Callout tone="info" title="Sin atención programada hoy">
          {availability.data?.blocker_message ?? "La sede no tiene horario de atención para hoy."}
        </Callout>
      )}

      <div className="grid gap-5 xl:grid-cols-[minmax(360px,420px)_minmax(0,1fr)]">
        <div className="space-y-4 xl:sticky xl:top-22 xl:self-start">
          {issued && <TicketIssued appointment={issued} onDismiss={() => setIssued(null)} />}
          {can("worker:lookup") && (
            <RegisterPanel
              ref={registerRef}
              siteId={site.id}
              availability={availability.data}
              onRegistered={(appointment) => {
                setIssued(appointment);
                notify.success(`Turno ${appointment.ticket_code} registrado`, appointment.worker.display_name);
              }}
            />
          )}
        </div>
        <div className="min-w-0">
          {data ? (
            <QueueBoard
              queue={data}
              onAction={handleAction}
              onOpen={(a) => setDetailId(a.public_id)}
              onCallNext={handleCallNext}
              callingNext={callNext.isPending}
              canOperate={canOperate}
              pendingId={transition.isPending ? (transition.variables?.appointment.public_id ?? null) : null}
            />
          ) : queue.isLoading ? (
            <div className="space-y-4">
              <Skeleton className="h-16 rounded-2xl" />
              <Skeleton className="h-80 rounded-[var(--radius-card)]" />
            </div>
          ) : (
            <Callout tone="info">
              <CalendarX2 className="mr-1 inline size-4" /> No hay información de la cola.
            </Callout>
          )}
        </div>
      </div>

      {dialog && <ReasonActionDialog appointment={dialog.appointment} action={dialog.action} onClose={() => setDialog(null)} />}
      <AppointmentDrawer appointmentId={detailId} onClose={() => setDetailId(null)} />
    </div>
  );
}
