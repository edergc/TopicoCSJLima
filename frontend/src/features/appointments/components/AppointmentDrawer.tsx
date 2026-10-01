import { Mail, RotateCw } from "lucide-react";

import { useAuth } from "@/shared/auth/AuthProvider";
import { CHANNEL_LABEL, statusStyle } from "@/shared/lib/status";
import { fmt } from "@/shared/lib/format";
import { cn } from "@/shared/lib/cn";
import { Badge, Button, DefinitionList, Drawer, Skeleton, StatusBadge } from "@/shared/ui";

import { useAppointment, useAppointmentEvents, useAppointmentNotifications, useResendNotification } from "../api";

const EVENT_LABEL: Record<string, string> = {
  REGISTER: "Registrado",
  ACTIVATE: "Ingresó a la cola del día",
  CALL: "Llamado",
  REQUEUE: "Devuelto a la cola",
  START: "Inicio de atención",
  FINISH: "Atención finalizada",
  CANCEL: "Cancelado",
  NO_SHOW: "No se presentó",
  VOID: "Anulado",
  MIGRATE: "Migrado del histórico",
};

const NOTIFICATION_LABEL: Record<string, string> = {
  APPT_REGISTERED: "Confirmación de registro",
  APPT_UPCOMING: "Aviso de proximidad",
  APPT_CALLED: "Llamado",
  APPT_CANCELLED: "Cancelación",
};

const NOTIFICATION_TONE = { SENT: "success", PENDING: "info", SENDING: "info", FAILED: "danger", SKIPPED: "neutral", CANCELLED: "neutral" } as const;
const NOTIFICATION_STATUS: Record<string, string> = {
  SENT: "Enviado",
  PENDING: "Pendiente",
  SENDING: "Enviando",
  FAILED: "Fallido",
  SKIPPED: "No enviado",
  CANCELLED: "Cancelado",
};

/** Detalle de una atención: datos, línea de tiempo (trazabilidad) y correos enviados. */
export function AppointmentDrawer({ appointmentId, onClose }: { appointmentId: string | null; onClose: () => void }) {
  const { can } = useAuth();
  const { data: appointment } = useAppointment(appointmentId);
  const { data: events, isLoading: loadingEvents } = useAppointmentEvents(appointmentId);
  const canSeeNotifications = can("notification:read");
  const { data: notifications } = useAppointmentNotifications(appointmentId, canSeeNotifications);
  const resend = useResendNotification();

  return (
    <Drawer
      open={Boolean(appointmentId)}
      onOpenChange={(open) => !open && onClose()}
      title={
        appointment ? (
          <span className="flex items-center gap-3">
            <span className="tabular">{appointment.ticket_code}</span>
            <StatusBadge status={appointment.status} />
          </span>
        ) : (
          "Atención"
        )
      }
      description={appointment ? `${appointment.site_name} · ${fmt.date(appointment.service_date)}` : undefined}
    >
      {!appointment ? (
        <Skeleton className="h-48" />
      ) : (
        <div className="space-y-8">
          <section>
            <h3 className="mb-3 text-xs font-semibold tracking-wide text-ink-soft uppercase">Trabajador</h3>
            <DefinitionList
              items={[
                ["Nombre", <span className="font-medium">{appointment.worker.display_name}</span>],
                ["DNI", <span className="tabular">{appointment.worker.document_number}</span>],
                ["Dependencia", appointment.worker.department_name ?? "—"],
                ["Correo", appointment.worker.has_email ? "Registrado" : "Sin correo registrado"],
              ]}
            />
          </section>

          <section>
            <h3 className="mb-3 text-xs font-semibold tracking-wide text-ink-soft uppercase">Solicitud</h3>
            <DefinitionList
              items={[
                ["Canal", CHANNEL_LABEL[appointment.channel] ?? appointment.channel],
                ["Registrado", fmt.dateTime(appointment.registered_at)],
                ["Llamados", appointment.call_count],
                ...(appointment.doctor_name ? ([["Médico", appointment.doctor_name]] as [string, string][]) : []),
                ...(appointment.close_reason
                  ? ([["Motivo de cierre", appointment.close_reason.label]] as [string, string][])
                  : []),
                ...(appointment.close_note ? ([["Observación de cierre", appointment.close_note]] as [string, string][]) : []),
                ...(appointment.admin_note ? ([["Observación", appointment.admin_note]] as [string, string][]) : []),
              ]}
            />
          </section>

          <section>
            <h3 className="mb-3 text-xs font-semibold tracking-wide text-ink-soft uppercase">Línea de tiempo</h3>
            {loadingEvents ? (
              <Skeleton className="h-32" />
            ) : (
              <ol className="relative space-y-4 border-l border-line pl-5">
                {events?.map((event, index) => {
                  const style = statusStyle(event.to_status);
                  return (
                    <li key={index} className="relative">
                      <span className={cn("absolute top-1.5 -left-[25px] size-2.5 rounded-full ring-4 ring-panel", style.dot)} aria-hidden />
                      <p className="text-sm font-medium text-ink">{EVENT_LABEL[event.action] ?? event.action}</p>
                      <p className="text-[13px] text-ink-soft">
                        <span className="tabular">{fmt.dateTime(event.occurred_at)}</span> · {event.user_name}
                      </p>
                      {(event.reason_label || event.note) && (
                        <p className="mt-1 text-[13px] text-ink-muted">
                          {event.reason_label}
                          {event.reason_label && event.note && " — "}
                          {event.note}
                        </p>
                      )}
                    </li>
                  );
                })}
              </ol>
            )}
          </section>

          {canSeeNotifications && (
            <section>
              <h3 className="mb-3 text-xs font-semibold tracking-wide text-ink-soft uppercase">Correos</h3>
              {notifications?.length === 0 && <p className="text-sm text-ink-soft">Sin notificaciones.</p>}
              <ul className="space-y-2">
                {notifications?.map((n) => (
                  <li key={n.id} className="flex items-center gap-3 rounded-xl border border-line px-3 py-2.5">
                    <Mail className="size-4 shrink-0 text-ink-soft" aria-hidden />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium">{NOTIFICATION_LABEL[n.template_code] ?? n.template_code}</p>
                      <p className="truncate text-xs text-ink-soft">
                        {n.recipient_masked ?? "—"} · {fmt.dateTime(n.sent_at ?? n.created_at)}
                        {n.last_error && ` · ${n.last_error}`}
                      </p>
                    </div>
                    <Badge tone={NOTIFICATION_TONE[n.status as keyof typeof NOTIFICATION_TONE] ?? "neutral"}>
                      {NOTIFICATION_STATUS[n.status] ?? n.status}
                    </Badge>
                    {can("notification:resend") && ["FAILED", "SENT"].includes(n.status) && appointment.worker.has_email && (
                      <Button variant="ghost" size="sm" loading={resend.isPending} onClick={() => resend.mutate(n.id)} icon={<RotateCw className="size-3.5" />}>
                        Reenviar
                      </Button>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      )}
    </Drawer>
  );
}
