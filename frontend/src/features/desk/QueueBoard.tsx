import {
  BellRing,
  CheckCheck,
  ChevronDown,
  Clock3,
  MoreHorizontal,
  Play,
  Stethoscope,
  Undo2,
  UserX,
  Users,
  XCircle,
} from "lucide-react";
import { useState } from "react";

import type { Appointment, AppointmentAction, Queue } from "@/shared/api/types";
import { cn } from "@/shared/lib/cn";
import { countdown, fmt, formatDuration, minutesSince } from "@/shared/lib/format";
import { useNow } from "@/shared/lib/hooks";
import { ACTION_LABEL } from "@/shared/lib/status";
import { Badge, Button, Card, EmptyState, IconButton, Kbd, Menu, MenuContent, MenuItem, MenuSeparator, MenuTrigger, StatusBadge } from "@/shared/ui";

type Act = (appointment: Appointment, action: AppointmentAction) => void;

interface Props {
  queue: Queue;
  onAction: Act;
  onOpen: (appointment: Appointment) => void;
  onCallNext: () => void;
  callingNext: boolean;
  canOperate: boolean;
  pendingId: string | null;
}

function InServiceCard({ appointment, onAction, onOpen, busy }: { appointment: Appointment; onAction: Act; onOpen: Props["onOpen"]; busy: boolean }) {
  const now = useNow(15_000);
  const elapsed = minutesSince(appointment.started_at, now);
  return (
    <div className="flex flex-wrap items-center gap-4 rounded-xl border border-status-inservice/20 bg-status-inservice-bg/70 p-4">
      <div className="grid size-12 place-items-center rounded-xl bg-status-inservice text-white">
        <Stethoscope className="size-6" aria-hidden />
      </div>
      <button type="button" onClick={() => onOpen(appointment)} className="min-w-0 flex-1 text-left">
        <p className="flex items-center gap-2">
          <span className="tabular text-2xl font-bold tracking-tight whitespace-nowrap text-ink">{appointment.ticket_code}</span>
          <StatusBadge status="EN_ATENCION" size="sm" />
        </p>
        <p className="truncate text-sm font-medium text-ink">{appointment.worker.display_name}</p>
        <p className="text-[13px] text-ink-muted">
          Desde las {fmt.time(appointment.started_at)} · {formatDuration(elapsed)}
        </p>
      </button>
      {appointment.allowed_actions.includes("FINISH") && (
        <Button size="lg" onClick={() => onAction(appointment, "FINISH")} loading={busy} icon={<CheckCheck className="size-5" />}>
          Finalizar atención
        </Button>
      )}
    </div>
  );
}

function CalledCard({ appointment, onAction, onOpen, busy }: { appointment: Appointment; onAction: Act; onOpen: Props["onOpen"]; busy: boolean }) {
  const now = useNow(1000);
  const remaining = countdown(appointment.tolerance_expires_at, now);
  const can = (a: AppointmentAction) => appointment.allowed_actions.includes(a);
  return (
    <div className="flex flex-wrap items-center gap-4 rounded-xl border border-status-called/20 bg-status-called-bg/70 p-4">
      <div className="grid size-12 animate-pulse-ring place-items-center rounded-xl bg-status-called text-white">
        <BellRing className="size-6" aria-hidden />
      </div>
      <button type="button" onClick={() => onOpen(appointment)} className="min-w-0 flex-1 text-left">
        <p className="flex items-center gap-2">
          <span className="tabular text-2xl font-bold tracking-tight whitespace-nowrap text-ink">{appointment.ticket_code}</span>
          <StatusBadge status="LLAMADO" size="sm" />
          {appointment.call_count > 1 && <Badge tone="info">{appointment.call_count}° llamado</Badge>}
        </p>
        <p className="truncate text-sm font-medium text-ink">{appointment.worker.display_name}</p>
        <p className={cn("tabular text-[13px]", remaining ? "text-ink-muted" : "font-medium text-status-noshow")}>
          Llamado a las {fmt.time(appointment.called_at)} ·{" "}
          {remaining ? `tolerancia ${remaining}` : "tolerancia vencida"}
        </p>
      </button>
      <div className="flex flex-wrap items-center gap-2">
        {can("START") && (
          <Button onClick={() => onAction(appointment, "START")} loading={busy} icon={<Play className="size-4" />}>
            Iniciar atención
          </Button>
        )}
        {can("NO_SHOW") && !remaining && (
          <Button variant="secondary" onClick={() => onAction(appointment, "NO_SHOW")} icon={<UserX className="size-4" />}>
            No se presentó
          </Button>
        )}
        <Menu>
          <MenuTrigger asChild>
            <IconButton label="Más acciones" variant="secondary" icon={<MoreHorizontal className="size-4" />} />
          </MenuTrigger>
          <MenuContent>
            {can("REQUEUE") && (
              <MenuItem onSelect={() => onAction(appointment, "REQUEUE")}>
                <Undo2 className="size-4" /> Devolver a la cola
              </MenuItem>
            )}
            {can("NO_SHOW") && (
              <MenuItem disabled={Boolean(remaining)} onSelect={() => onAction(appointment, "NO_SHOW")}>
                <UserX className="size-4" /> No se presentó {remaining && `(en ${remaining})`}
              </MenuItem>
            )}
            {can("CANCEL") && (
              <>
                <MenuSeparator />
                <MenuItem danger onSelect={() => onAction(appointment, "CANCEL")}>
                  <XCircle className="size-4" /> Cancelar atención
                </MenuItem>
              </>
            )}
          </MenuContent>
        </Menu>
      </div>
    </div>
  );
}

function WaitingRow({ appointment, index, onAction, onOpen }: { appointment: Appointment; index: number; onAction: Act; onOpen: Props["onOpen"] }) {
  const can = (a: AppointmentAction) => appointment.allowed_actions.includes(a);
  return (
    <li
      className={cn(
        "group flex items-center gap-3 border-b border-line px-4 py-3 last:border-b-0 sm:gap-4 sm:px-5",
        index === 0 && "bg-status-waiting-bg/40",
      )}
    >
      <span className="tabular w-16 shrink-0 text-lg font-bold tracking-tight whitespace-nowrap text-ink">{appointment.ticket_code}</span>
      <button type="button" onClick={() => onOpen(appointment)} className="min-w-0 flex-1 text-left">
        <p className="truncate text-sm font-medium text-ink group-hover:text-brand-800">{appointment.worker.display_name}</p>
        <p className="truncate text-xs text-ink-soft">
          {appointment.worker.department_name ?? "Sin dependencia"}
          {!appointment.worker.has_email && " · sin correo"}
        </p>
      </button>
      <div className="hidden w-24 shrink-0 text-right sm:block">
        <p className="tabular text-xs text-ink-soft">Registro {fmt.time(appointment.registered_at)}</p>
        <p className="tabular text-sm font-medium text-ink">
          {appointment.estimated_at ? `~ ${fmt.time(appointment.estimated_at)}` : "Fuera de horario"}
        </p>
      </div>
      {index === 0 ? <Badge tone="warning">Siguiente</Badge> : <StatusBadge status={appointment.status} size="sm" className="hidden md:inline-flex" />}
      <Menu>
        <MenuTrigger asChild>
          <IconButton label={`Acciones del turno ${appointment.ticket_code}`} size="sm" icon={<MoreHorizontal className="size-4" />} />
        </MenuTrigger>
        <MenuContent>
          {can("CALL") && (
            <MenuItem onSelect={() => onAction(appointment, "CALL")}>
              <BellRing className="size-4" /> Llamar a este turno
            </MenuItem>
          )}
          <MenuItem onSelect={() => onOpen(appointment)}>
            <Clock3 className="size-4" /> Ver detalle
          </MenuItem>
          {(can("CANCEL") || can("VOID")) && <MenuSeparator />}
          {can("CANCEL") && (
            <MenuItem danger onSelect={() => onAction(appointment, "CANCEL")}>
              <XCircle className="size-4" /> {ACTION_LABEL.CANCEL}
            </MenuItem>
          )}
          {can("VOID") && (
            <MenuItem danger onSelect={() => onAction(appointment, "VOID")}>
              <XCircle className="size-4" /> Anular (error de registro)
            </MenuItem>
          )}
        </MenuContent>
      </Menu>
    </li>
  );
}

export function QueueBoard({ queue, onAction, onOpen, onCallNext, callingNext, canOperate, pendingId }: Props) {
  const [showClosed, setShowClosed] = useState(false);
  const finished = [...queue.finished, ...queue.closed].sort((a, b) => b.ticket_number - a.ticket_number);
  const next = queue.waiting[0];

  return (
    <div className="space-y-4">
      {(queue.in_service.length > 0 || queue.called.length > 0) && (
        <section aria-label="Atención en curso" className="space-y-3">
          {queue.in_service.map((a) => (
            <InServiceCard key={a.public_id} appointment={a} onAction={onAction} onOpen={onOpen} busy={pendingId === a.public_id} />
          ))}
          {queue.called.map((a) => (
            <CalledCard key={a.public_id} appointment={a} onAction={onAction} onOpen={onOpen} busy={pendingId === a.public_id} />
          ))}
        </section>
      )}

      {canOperate && (
        <Button
          size="xl"
          className="w-full justify-between"
          onClick={onCallNext}
          loading={callingNext}
          disabled={!next}
          icon={<BellRing className="size-6" aria-hidden />}
          trailing={
            <span className="ml-auto flex items-center gap-3">
              {next && <span className="tabular rounded-lg bg-white/15 px-3 py-1 text-xl">{next.ticket_code}</span>}
              <Kbd>F4</Kbd>
            </span>
          }
        >
          {next ? "LLAMAR SIGUIENTE" : "No hay trabajadores en espera"}
        </Button>
      )}

      <Card>
        <div className="flex items-center justify-between border-b border-line px-5 py-3.5">
          <h2 className="flex items-center gap-2 text-[15px] font-semibold tracking-tight">
            <Users className="size-[18px] text-status-waiting" aria-hidden />
            En espera
            <span className="tabular rounded-full bg-status-waiting-bg px-2 py-0.5 text-xs font-semibold text-status-waiting">
              {queue.waiting.length}
            </span>
          </h2>
          <p className="hidden text-xs text-ink-soft sm:block">Orden de registro · hora estimada referencial</p>
        </div>
        {queue.waiting.length === 0 ? (
          <EmptyState icon={Users} title="Nadie en espera" description="Los nuevos registros aparecerán aquí en orden de llegada." />
        ) : (
          <ol aria-label="Cola de espera">
            {queue.waiting.map((a, i) => (
              <WaitingRow key={a.public_id} appointment={a} index={i} onAction={onAction} onOpen={onOpen} />
            ))}
          </ol>
        )}
      </Card>

      {finished.length > 0 && (
        <Card>
          <button
            type="button"
            onClick={() => setShowClosed((v) => !v)}
            aria-expanded={showClosed}
            className="flex w-full items-center justify-between px-5 py-3.5 text-left"
          >
            <span className="text-sm font-semibold text-ink">
              Finalizados y cerrados <span className="tabular font-normal text-ink-soft">({finished.length})</span>
            </span>
            <ChevronDown className={cn("size-4 text-ink-soft transition-transform", showClosed && "rotate-180")} aria-hidden />
          </button>
          {showClosed && (
            <ul className="border-t border-line">
              {finished.map((a) => (
                <li key={a.public_id}>
                  <button
                    type="button"
                    onClick={() => onOpen(a)}
                    className="flex w-full items-center gap-4 border-b border-line px-5 py-2.5 text-left last:border-b-0 hover:bg-surface"
                  >
                    <span className="tabular w-16 font-semibold text-ink-muted">{a.ticket_code}</span>
                    <span className="min-w-0 flex-1 truncate text-sm text-ink-muted">{a.worker.display_name}</span>
                    <span className="tabular hidden text-xs text-ink-soft sm:block">
                      {fmt.time(a.finished_at ?? a.closed_at)}
                    </span>
                    <StatusBadge status={a.status} size="sm" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}
    </div>
  );
}
