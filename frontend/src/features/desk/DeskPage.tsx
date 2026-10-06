import { AlertTriangle, CalendarX2, MonitorPlay, RefreshCw } from "lucide-react";
import { useRef, useState } from "react";

import { AppointmentDrawer } from "@/features/appointments/components/AppointmentDrawer";
import { ACTIONS_WITH_REASON, ReasonActionDialog } from "@/features/appointments/components/ReasonActionDialog";
import { useAvailability, useCallNext, useDoctors, useQueue, useRooms, useTransition } from "@/features/appointments/api";
import type { Appointment, AppointmentAction } from "@/shared/api/types";
import { useAuth } from "@/shared/auth/AuthProvider";
import { useSite } from "@/shared/auth/SiteProvider";
import { cn } from "@/shared/lib/cn";
import { fmt } from "@/shared/lib/format";
import { useDocumentTitle, useHotkey } from "@/shared/lib/hooks";
import { errorMessage, notify } from "@/shared/lib/notify";
import { Button, Callout, Select, Skeleton } from "@/shared/ui";

import { DayControls } from "./DayControls";
import { DoctorPickerDialog } from "./DoctorPickerDialog";
import { PriorityDialog } from "./PriorityDialog";
import { useWorkingRoom } from "./useWorkingRoom";
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
  const [starting, setStarting] = useState<Appointment | null>(null);
  const [priorityFor, setPriorityFor] = useState<Appointment | null>(null);
  const doctors = useDoctors(siteId);
  // Presentes hoy (activos y sin ausencia); los de turno ahora van primero.
  const presentDoctors = doctors.data?.filter((d) => d.is_active && d.present_today) ?? [];
  const onDuty = presentDoctors.filter((d) => d.on_duty_now);
  const doctorPool = onDuty.length ? onDuty : presentDoctors;
  const pickerDoctors = [...onDuty, ...presentDoctors.filter((d) => !d.on_duty_now)];
  const rooms = useRooms(siteId);
  const activeRooms = rooms.data?.filter((r) => r.is_active) ?? [];
  const [roomId, setRoomId] = useWorkingRoom(siteId, activeRooms);
  // Con varios consultorios, la encargada indica a cuál llama (se recuerda en este equipo).
  const needsRoom = activeRooms.length > 1 && roomId === null;
  const roomName = activeRooms.find((r) => r.id === roomId)?.name;
  const warnRoom = () => notify.warning("Seleccione su consultorio", "Indique arriba a qué consultorio se llama a las personas.");

  const canOperate = can("appointment:operate");

  const handleAction = (appointment: Appointment, action: AppointmentAction) => {
    if (ACTIONS_WITH_REASON.has(action)) {
      setDialog({ appointment, action });
      return;
    }
    // Con más de un médico activo, se elige quién atiende (con uno solo, el servidor lo asigna).
    if (action === "START" && doctorPool.length > 1) {
      setStarting(appointment);
      return;
    }
    if (action === "CALL" && needsRoom) {
      warnRoom();
      return;
    }
    transition.mutate(
      { appointment, action, body: action === "CALL" && roomId ? { room_id: roomId } : undefined },
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
    if (needsRoom) {
      warnRoom();
      return;
    }
    callNext.mutate(roomId, {
      onSuccess: (a) =>
        notify.info(
          `Turno ${a.ticket_code} llamado`,
          `${a.worker.display_name} — indíquele que se acerque ${a.room_name ? `al ${a.room_name}` : "al tópico"}.`,
        ),
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
        <div className="flex items-center gap-3 text-[0.8125rem] text-ink-soft">
          {availability.data?.blocks.map((b) => (
            <span key={b.block} className="tabular hidden rounded-lg bg-panel px-2.5 py-1 ring-1 ring-line md:inline">
              {b.block === "AM" ? "Mañana" : "Tarde"} {b.start.slice(0, 5)}–{b.end.slice(0, 5)}
            </span>
          ))}
          {activeRooms.length > 1 && (
            <label className={cn("inline-flex items-center gap-2", needsRoom && "font-semibold text-warning")}>
              Consultorio
              <Select
                aria-label="Consultorio al que llama"
                value={roomId ?? ""}
                onChange={(e) => setRoomId(e.target.value ? Number(e.target.value) : null)}
                className={cn("h-8 w-auto py-0 text-[0.8125rem]", needsRoom && "ring-2 ring-warning")}
              >
                <option value="">Seleccione…</option>
                {activeRooms.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </Select>
            </label>
          )}
          {activeRooms.length === 1 && roomName && <span className="hidden md:inline">{roomName}</span>}
          <a
            href={`/pantalla/${site.code.toLowerCase()}`}
            target="_blank"
            rel="noopener"
            title="Abrir la pantalla de turnos de la sala de espera (TV)"
            className="inline-flex items-center gap-1.5 rounded-lg bg-panel px-2.5 py-1 font-medium text-brand-700 ring-1 ring-line hover:ring-brand-300"
          >
            <MonitorPlay className="size-3.5" aria-hidden /> Pantalla de sala
          </a>
          <span className={cn("inline-flex items-center gap-1.5", queue.isFetching && "text-brand-700")} aria-live="polite">
            <RefreshCw className={cn("size-3.5", queue.isFetching && "animate-spin")} aria-hidden />
            {data ? `Actualizado ${fmt.time(data.generated_at)}` : "Cargando…"}
          </span>
        </div>
      </div>

      {data && <DayControls siteId={site.id} queue={data} />}

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
              className="inline-flex items-center gap-1.5 rounded-lg bg-status-waiting-bg px-3 py-1.5 text-[0.8125rem] font-medium text-amber-900 ring-1 ring-status-waiting/25"
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
              priorityEnabled={data?.priority_enabled ?? false}
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
              onPriority={can("appointment:create") ? setPriorityFor : undefined}
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

      {priorityFor && <PriorityDialog appointment={priorityFor} onClose={() => setPriorityFor(null)} />}
      {starting && (
        <DoctorPickerDialog
          appointment={starting}
          doctors={pickerDoctors}
          loading={transition.isPending}
          onClose={() => setStarting(null)}
          onConfirm={(doctorId) =>
            transition.mutate({ appointment: starting, action: "START", body: { doctor_id: doctorId } }, { onSuccess: () => setStarting(null) })
          }
        />
      )}
      {dialog && <ReasonActionDialog appointment={dialog.appointment} action={dialog.action} onClose={() => setDialog(null)} />}
      <AppointmentDrawer appointmentId={detailId} onClose={() => setDetailId(null)} />
    </div>
  );
}
