import {
  AlertTriangle,
  CheckCircle2,
  Mail,
  MailX,
  MessageSquarePlus,
  Phone,
  PhoneOff,
  Ticket,
  UserRoundSearch,
  XCircle,
} from "lucide-react";
import { forwardRef, useImperativeHandle, useRef, useState } from "react";

import type { Appointment, Availability, Eligibility } from "@/shared/api/types";
import { useAuth } from "@/shared/auth/AuthProvider";
import { cn } from "@/shared/lib/cn";
import { fmt } from "@/shared/lib/format";
import { errorMessage } from "@/shared/lib/notify";
import { Button, Callout, Card, Field, Kbd, Segmented, Skeleton, StatusBadge, Textarea } from "@/shared/ui";

import { useEligibility, useRegisterAppointment } from "@/features/appointments/api";

export interface RegisterPanelHandle {
  focus: () => void;
}

interface Props {
  siteId: number;
  availability: Availability | undefined;
  onRegistered: (appointment: Appointment) => void;
}

function EligibilityCard({ data }: { data: Eligibility }) {
  const worker = data.worker;
  const ok = data.eligible;
  return (
    <div
      className={cn(
        "animate-slide-up rounded-xl border p-4",
        ok ? "border-status-done/25 bg-status-done-bg/60" : "border-status-noshow/25 bg-status-noshow-bg/60",
      )}
      aria-live="polite"
    >
      <p className={cn("flex items-center gap-2 text-sm font-semibold", ok ? "text-status-done" : "text-status-noshow")}>
        {ok ? <CheckCircle2 className="size-4" aria-hidden /> : <XCircle className="size-4" aria-hidden />}
        {ok ? "Habilitado · EPS Rímac vigente" : data.message}
      </p>
      {worker ? (
        <div className="mt-3">
          <p className="text-[17px] leading-snug font-semibold tracking-tight text-ink">
            {worker.paternal_surname} {worker.maternal_surname ?? ""}, {worker.first_names}
          </p>
          <p className="mt-0.5 text-sm text-ink-muted">
            <span className="tabular">DNI {worker.document_number}</span>
            {worker.department_name && <> · {worker.department_name}</>}
          </p>
          <div className="mt-2.5 flex flex-wrap gap-3 text-[13px] text-ink-muted">
            <span className="inline-flex items-center gap-1.5">
              {worker.has_email ? <Mail className="size-3.5" /> : <MailX className="size-3.5 text-status-waiting" />}
              {worker.has_email ? "Recibirá notificaciones por correo" : "Sin correo: no recibirá notificaciones"}
            </span>
            <span className="inline-flex items-center gap-1.5">
              {worker.has_phone ? <Phone className="size-3.5" /> : <PhoneOff className="size-3.5" />}
              {worker.has_phone ? "Teléfono registrado" : "Sin teléfono"}
            </span>
          </div>
        </div>
      ) : (
        <p className="mt-1 text-[13px] text-ink-muted">
          Verifique el número. Si el trabajador debería estar habilitado, la relación de EPS Rímac debe actualizarse por
          importación.
        </p>
      )}
    </div>
  );
}

export const RegisterPanel = forwardRef<RegisterPanelHandle, Props>(function RegisterPanel({ siteId, availability, onRegistered }, ref) {
  const { can } = useAuth();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dni, setDni] = useState("");
  const [channel, setChannel] = useState<"PHONE" | "WALK_IN">("PHONE");
  const [note, setNote] = useState("");
  const [showNote, setShowNote] = useState(false);
  const eligibility = useEligibility(dni);
  const registerMutation = useRegisterAppointment();

  useImperativeHandle(ref, () => ({ focus: () => inputRef.current?.select() }), []);

  const reset = () => {
    setDni("");
    setNote("");
    setShowNote(false);
    registerMutation.reset();
    requestAnimationFrame(() => inputRef.current?.focus());
  };

  const data = eligibility.data;
  const active = data?.active_appointment;
  const blocked = availability && !availability.can_register ? availability.blocker_message : null;
  const canRegister = can("appointment:create") && data?.eligible && !active && !blocked;

  const submit = () => {
    if (!canRegister || !data) return;
    registerMutation.mutate(
      { site_id: siteId, document_number: data.document_number, channel, admin_note: note.trim() || null },
      {
        onSuccess: (appointment) => {
          onRegistered(appointment);
          reset();
        },
      },
    );
  };

  return (
    <Card className="overflow-hidden">
      <div className="flex items-center justify-between border-b border-line px-5 py-4">
        <h2 className="flex items-center gap-2 text-[15px] font-semibold tracking-tight">
          <UserRoundSearch className="size-[18px] text-brand-700" aria-hidden />
          Registrar atención
        </h2>
        <span className="hidden items-center gap-1.5 text-xs text-ink-soft sm:flex">
          Buscar <Kbd>F2</Kbd>
        </span>
      </div>
      <form
        className="space-y-4 p-5"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <div>
          <label htmlFor="dni" className="text-[13px] font-medium">
            DNI del trabajador
          </label>
          <input
            ref={inputRef}
            id="dni"
            value={dni}
            onChange={(e) => {
              setDni(e.target.value.replace(/\D/g, "").slice(0, 8));
              registerMutation.reset();
            }}
            inputMode="numeric"
            autoComplete="off"
            autoFocus
            placeholder="00000000"
            aria-describedby="dni-help"
            className="tabular mt-1.5 h-14 w-full rounded-xl border border-line-strong bg-panel px-4 text-[26px] font-semibold tracking-[0.18em] text-ink placeholder:text-line-strong focus:border-brand-600 focus:ring-4 focus:ring-brand-600/12 focus:outline-none"
          />
          <p id="dni-help" className="mt-1.5 text-xs text-ink-soft">
            {dni.length > 0 && dni.length < 8 ? `${8 - dni.length} dígito(s) restante(s)` : "La verificación se realiza al completar los 8 dígitos."}
          </p>
        </div>

        {eligibility.isFetching && !data && <Skeleton className="h-28" />}
        {eligibility.isError && <Callout tone="danger">{errorMessage(eligibility.error)}</Callout>}
        {data && dni === data.document_number && (
          <>
            <EligibilityCard data={data} />
            {active && (
              <Callout tone="warning" title={`Ya tiene el turno ${active.ticket_code}`}>
                <span className="inline-flex flex-wrap items-center gap-2">
                  {active.site_name} · {fmt.date(active.service_date)} <StatusBadge status={active.status} size="sm" />
                </span>
              </Callout>
            )}
          </>
        )}

        {data?.eligible && !active && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-[13px] font-medium">Canal de la solicitud</span>
              <Segmented
                label="Canal de la solicitud"
                value={channel}
                onChange={setChannel}
                options={[
                  { value: "PHONE", label: "Teléfono" },
                  { value: "WALK_IN", label: "Presencial" },
                ]}
              />
            </div>
            {showNote ? (
              <Field label="Observación administrativa" hint="No registre síntomas, diagnósticos ni información clínica.">
                <Textarea value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} rows={2} autoFocus />
              </Field>
            ) : (
              <button
                type="button"
                onClick={() => setShowNote(true)}
                className="inline-flex items-center gap-1.5 text-[13px] font-medium text-brand-700 hover:text-brand-800"
              >
                <MessageSquarePlus className="size-4" aria-hidden /> Agregar observación administrativa
              </button>
            )}
          </div>
        )}

        {blocked && data?.eligible && !active && (
          <Callout tone="danger" title="No es posible registrar">
            {blocked}
          </Callout>
        )}
        {registerMutation.isError && <Callout tone="danger">{errorMessage(registerMutation.error)}</Callout>}

        <Button
          type="submit"
          size="xl"
          className="w-full"
          disabled={!canRegister}
          loading={registerMutation.isPending}
          icon={<Ticket className="size-5" aria-hidden />}
        >
          Registrar turno
        </Button>
        {availability && availability.can_register && availability.available <= 2 && (
          <p className="flex items-center justify-center gap-1.5 text-[13px] text-status-waiting">
            <AlertTriangle className="size-3.5" aria-hidden />
            Quedan {availability.available} cupo(s) para hoy
          </p>
        )}
      </form>
    </Card>
  );
});
