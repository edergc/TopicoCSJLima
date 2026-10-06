import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Coffee, FileDown, Lock, Play } from "lucide-react";
import { useState } from "react";

import { api } from "@/shared/api/client";
import type { DayClose, Queue } from "@/shared/api/types";
import { useAuth } from "@/shared/auth/AuthProvider";
import { cn } from "@/shared/lib/cn";
import { fmt } from "@/shared/lib/format";
import { notify } from "@/shared/lib/notify";
import { Button, Callout, ConfirmDialog, Field, Modal, Select } from "@/shared/ui";

const REASONS = ["Refrigerio", "Emergencia", "Reunión", "Atención fuera del tópico", "Otro"];
const MINUTES = [10, 15, 30, 45, 60, 90, 120];

function useRefreshQueue() {
  const queryClient = useQueryClient();
  return () => {
    void queryClient.invalidateQueries({ queryKey: ["queue"] });
    void queryClient.invalidateQueries({ queryKey: ["availability"] });
  };
}

/** Botones de la jornada en la Mesa: pausar/reanudar la atención y cerrar el día. */
export function DayControls({ siteId, queue }: { siteId: number; queue: Queue }) {
  const { can } = useAuth();
  const refresh = useRefreshQueue();
  const [pausing, setPausing] = useState(false);
  const [closing, setClosing] = useState(false);
  const open = queue.day_status === "OPEN";

  const resume = useMutation({
    mutationFn: () => api.post(`/sites/${siteId}/resume`),
    onSuccess: () => (notify.success("Atención reanudada"), refresh()),
    onError: (e) => notify.error(e),
  });

  return (
    <>
      {queue.pause && (
        <Callout
          tone="warning"
          title={`Atención en pausa · ${queue.pause.reason}`}
          action={
            can("appointment:operate") && (
              <Button size="sm" onClick={() => resume.mutate()} loading={resume.isPending} icon={<Play className="size-4" />}>
                Reanudar
              </Button>
            )
          }
        >
          La pantalla de sala indica que se retoma a las <b>{fmt.time(queue.pause.resume_at)}</b>; las horas estimadas ya consideran la pausa.
          Al llamar al siguiente, la pausa termina sola.
        </Callout>
      )}
      <div className="flex flex-wrap items-center gap-2">
        {can("appointment:operate") && open && !queue.pause && (
          <Button size="sm" variant="secondary" icon={<Coffee className="size-4" />} onClick={() => setPausing(true)}>
            Pausar atención
          </Button>
        )}
        {can("service_day:close") && open && (
          <Button size="sm" variant="secondary" icon={<Lock className="size-4" />} onClick={() => setClosing(true)}>
            Cerrar día
          </Button>
        )}
        {queue.day_status === "CLOSED" && <span className="text-[0.8125rem] font-medium text-ink-soft">Jornada cerrada</span>}
      </div>
      {pausing && <PauseDialog siteId={siteId} onClose={() => setPausing(false)} onDone={refresh} />}
      {closing && <CloseDayDialog siteId={siteId} queue={queue} onClose={() => setClosing(false)} onDone={refresh} />}
    </>
  );
}

function PauseDialog({ siteId, onClose, onDone }: { siteId: number; onClose: () => void; onDone: () => void }) {
  const [reason, setReason] = useState(REASONS[0]!);
  const [other, setOther] = useState("");
  const [minutes, setMinutes] = useState(30);
  const finalReason = reason === "Otro" ? other.trim() : reason;
  const pause = useMutation({
    mutationFn: () => api.post(`/sites/${siteId}/pause`, { reason: finalReason, minutes }),
    onSuccess: () => {
      notify.info("Atención en pausa", "La pantalla de sala ya muestra el aviso.");
      onDone();
      onClose();
    },
    onError: (e) => notify.error(e),
  });
  return (
    <Modal
      open
      onOpenChange={(o) => !o && onClose()}
      size="sm"
      title="Pausar la atención"
      description="La pantalla de sala mostrará el aviso y la hora de reanudación. Queda registrado en la auditoría."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button onClick={() => pause.mutate()} loading={pause.isPending} disabled={finalReason.length < 3} icon={<Coffee className="size-4" />}>
            Pausar
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Motivo">
          {REASONS.map((r) => (
            <button
              key={r}
              type="button"
              role="radio"
              aria-checked={reason === r}
              onClick={() => setReason(r)}
              className={cn(
                "rounded-lg px-3 py-1.5 text-sm ring-1 transition",
                reason === r ? "bg-brand-700 font-medium text-white ring-brand-700" : "bg-panel text-ink-muted ring-line hover:ring-line-strong",
              )}
            >
              {r}
            </button>
          ))}
        </div>
        {reason === "Otro" && (
          <Field label="Motivo">
            <input
              className="h-10 w-full rounded-lg border border-line-strong bg-panel px-3 text-sm"
              maxLength={150}
              value={other}
              onChange={(e) => setOther(e.target.value)}
              autoFocus
            />
          </Field>
        )}
        <Field label="Duración aproximada">
          <Select value={minutes} onChange={(e) => setMinutes(Number(e.target.value))}>
            {MINUTES.map((m) => (
              <option key={m} value={m}>
                {m < 60 ? `${m} minutos` : `${m / 60} hora${m > 60 ? "s" : ""}`}
              </option>
            ))}
          </Select>
        </Field>
      </div>
    </Modal>
  );
}

function CloseDayDialog({ siteId, queue, onClose, onDone }: { siteId: number; queue: Queue; onClose: () => void; onDone: () => void }) {
  const [result, setResult] = useState<DayClose | null>(null);
  const pending = queue.counts.registered + queue.counts.waiting + queue.counts.called;
  const close = useMutation({
    mutationFn: () => api.post<DayClose>(`/sites/${siteId}/service-days/${queue.service_date}/close`),
    onSuccess: (r) => {
      setResult(r);
      onDone();
    },
    onError: (e) => notify.error(e),
  });
  const downloadPdf = () =>
    void api
      .download("/reports/export", { report: "summary", format: "pdf", date_from: queue.service_date, date_to: queue.service_date, site_id: siteId })
      .catch((e) => notify.error(e));

  if (result) {
    return (
      <Modal
        open
        onOpenChange={(o) => !o && onClose()}
        size="sm"
        title="Jornada cerrada"
        footer={
          <>
            <Button variant="secondary" icon={<FileDown className="size-4" />} onClick={downloadPdf}>
              Descargar PDF del día
            </Button>
            <Button onClick={onClose}>Listo</Button>
          </>
        }
      >
        <ul className="space-y-1.5 text-sm">
          <li>
            Atendidos: <b className="tabular">{result.attended}</b>
          </li>
          <li>
            No presentados: <b className="tabular">{result.no_show}</b>
            {result.marked_no_show > 0 && <span className="text-ink-soft"> ({result.marked_no_show} marcados al cierre)</span>}
          </li>
          <li>
            Cancelados: <b className="tabular">{result.cancelled}</b>
          </li>
          <li className="pt-2 text-ink-muted">
            {result.summary_sent_to > 0
              ? `Se enviará el resumen en PDF a ${result.summary_sent_to} destinatario(s) por correo.`
              : "No hay supervisoras con correo registrado para enviar el resumen."}
          </li>
        </ul>
      </Modal>
    );
  }
  return (
    <ConfirmDialog
      open
      onOpenChange={(o) => !o && onClose()}
      tone="danger"
      title={`Cerrar el día ${fmt.date(queue.service_date)}`}
      description="Ya no se podrán registrar ni llamar turnos en esta fecha."
      confirmLabel="Cerrar día"
      loading={close.isPending}
      confirmDisabled={queue.counts.in_service > 0}
      onConfirm={() => close.mutate()}
    >
      <div className="space-y-2 text-sm">
        {queue.counts.in_service > 0 ? (
          <Callout tone="warning">Hay una atención en curso: finalícela antes de cerrar el día.</Callout>
        ) : pending > 0 ? (
          <p>
            Quedan <b>{pending}</b> persona(s) sin atender; se marcarán como <b>no presentadas</b> con el motivo «No fue atendido al cierre
            de la jornada».
          </p>
        ) : (
          <p>No quedan personas pendientes.</p>
        )}
        <p className="text-ink-muted">Se enviará el resumen del día en PDF a las supervisoras de la sede.</p>
      </div>
    </ConfirmDialog>
  );
}
