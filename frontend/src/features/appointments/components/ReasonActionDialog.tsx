import { useState } from "react";

import type { Appointment, AppointmentAction } from "@/shared/api/types";
import { cn } from "@/shared/lib/cn";
import { ConfirmDialog, Field, Skeleton, Textarea } from "@/shared/ui";

import { useReasons, useTransition } from "../api";

const CONFIG: Partial<
  Record<AppointmentAction, { type: string; title: string; confirm: string; tone: "danger" | "primary"; description: string; reasonRequired: boolean }>
> = {
  CANCEL: {
    type: "CANCEL",
    title: "Cancelar atención",
    confirm: "Cancelar atención",
    tone: "danger",
    description: "El cupo se liberará. El registro se conserva con el motivo indicado.",
    reasonRequired: true,
  },
  VOID: {
    type: "VOID",
    title: "Anular registro",
    confirm: "Anular registro",
    tone: "danger",
    description: "Use esta opción solo para corregir un error de registro. El cupo se liberará.",
    reasonRequired: true,
  },
  NO_SHOW: {
    type: "NO_SHOW",
    title: "Marcar como no presentado",
    confirm: "Marcar no presentado",
    tone: "danger",
    description: "El trabajador no acudió tras el llamado. El cupo se liberará.",
    reasonRequired: true,
  },
  REQUEUE: {
    type: "REQUEUE",
    title: "Devolver a la cola",
    confirm: "Devolver a la cola",
    tone: "primary",
    description: "Conserva su número de turno y su lugar en la cola.",
    reasonRequired: false,
  },
};

export const ACTIONS_WITH_REASON = new Set<AppointmentAction>(["CANCEL", "VOID", "NO_SHOW", "REQUEUE"]);

interface Props {
  appointment: Appointment;
  action: AppointmentAction;
  onClose: () => void;
}

/** Acción sensible con motivo del catálogo y observación administrativa opcional/obligatoria. */
export function ReasonActionDialog({ appointment, action, onClose }: Props) {
  const config = CONFIG[action]!;
  const { data: reasons, isLoading } = useReasons(config.type);
  const transition = useTransition();
  const [reasonId, setReasonId] = useState<number | null>(null);
  const [note, setNote] = useState("");
  const selected = reasons?.find((r) => r.id === reasonId) ?? null;
  const effectiveReason = selected ?? (reasons?.length === 1 ? reasons[0] : null);
  const noteRequired = Boolean(effectiveReason?.requires_note);
  const canConfirm = (!config.reasonRequired || effectiveReason !== null) && (!noteRequired || note.trim().length > 0);

  const confirm = () =>
    transition.mutate(
      { appointment, action, body: { reason_id: effectiveReason?.id ?? null, note: note.trim() || null } },
      { onSuccess: onClose },
    );

  return (
    <ConfirmDialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={`${config.title} · ${appointment.ticket_code}`}
      description={config.description}
      confirmLabel={config.confirm}
      tone={config.tone}
      loading={transition.isPending}
      confirmDisabled={!canConfirm}
      onConfirm={confirm}
    >
      <div className="space-y-4">
        <div className="rounded-xl bg-surface px-3 py-2.5 text-sm">
          <p className="font-medium text-ink">{appointment.worker.display_name}</p>
          <p className="text-ink-soft">DNI {appointment.worker.document_number}</p>
        </div>
        <fieldset>
          <legend className="mb-2 text-[0.8125rem] font-medium">
            Motivo{config.reasonRequired && <span className="text-brand-700"> *</span>}
          </legend>
          {isLoading ? (
            <Skeleton className="h-24" />
          ) : (
            <div className="space-y-1.5" role="radiogroup">
              {reasons?.map((reason) => {
                const checked = effectiveReason?.id === reason.id;
                return (
                  <label
                    key={reason.id}
                    className={cn(
                      "flex cursor-pointer items-center gap-3 rounded-lg border px-3 py-2.5 text-sm transition-colors",
                      checked ? "border-brand-600 bg-brand-50/60" : "border-line hover:bg-surface",
                    )}
                  >
                    <input
                      type="radio"
                      name="reason"
                      className="size-4 accent-brand-700"
                      checked={checked}
                      onChange={() => setReasonId(reason.id)}
                    />
                    {reason.label}
                  </label>
                );
              })}
            </div>
          )}
        </fieldset>
        <Field
          label="Observación administrativa"
          required={noteRequired}
          hint="No registre síntomas, diagnósticos ni información clínica."
        >
          <Textarea value={note} maxLength={300} onChange={(e) => setNote(e.target.value)} rows={2} />
        </Field>
      </div>
    </ConfirmDialog>
  );
}
