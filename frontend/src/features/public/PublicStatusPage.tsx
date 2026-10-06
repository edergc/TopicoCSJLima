import { useQuery } from "@tanstack/react-query";
import { MapPin, RefreshCw, Search, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { BrandMark } from "@/app/layout/BrandMark";
import { ApiError, api } from "@/shared/api/client";
import type { PublicTicketStatus } from "@/shared/api/types";
import { cn } from "@/shared/lib/cn";
import { fmt } from "@/shared/lib/format";
import { useDocumentTitle } from "@/shared/lib/hooks";
import { statusStyle } from "@/shared/lib/status";
import { Button, Callout, Field, Input, StatusBadge } from "@/shared/ui";

const MESSAGES: Record<string, string> = {
  REGISTRADO: "Su solicitud está registrada. El día de la atención ingresará a la cola.",
  EN_ESPERA: "Está en la cola. Le avisaremos por correo cuando su atención se aproxime.",
  LLAMADO: "¡Es su turno! Acérquese al tópico ahora.",
  EN_ATENCION: "Está siendo atendido.",
  ATENDIDO: "Su atención ha concluido.",
  CANCELADO: "Su solicitud fue cancelada.",
  NO_PRESENTADO: "Se registró que no se presentó al llamado. Comuníquese con el tópico si necesita una nueva atención.",
  ANULADO: "El registro fue anulado. Comuníquese con el tópico.",
};

function readTicketFromHash(): { dni: string; code: string } | null {
  const params = new URLSearchParams(window.location.hash.slice(1));
  const dni = params.get("dni") ?? "";
  const code = (params.get("turno") ?? "").toUpperCase();
  if (!/^\d{8}$/.test(dni) || !/^[A-Z]{1,3}-\d{3}$/.test(code)) return null;
  // No dejar el DNI visible en la barra de direcciones.
  window.history.replaceState(null, "", window.location.pathname);
  return { dni, code };
}

/**
 * Consulta pública (sin sesión), pensada para el celular del trabajador.
 * Exige DNI + código de turno; no muestra datos de otras personas.
 */
export default function PublicStatusPage() {
  useDocumentTitle("Consulta de turno");
  // Desde el QR del ticket: /consulta#dni=…&turno=… (el fragmento no viaja al servidor).
  const [fromQr] = useState(readTicketFromHash);
  const [dni, setDni] = useState(fromQr?.dni ?? "");
  const [code, setCode] = useState(fromQr?.code ?? "");
  const [submitted, setSubmitted] = useState<{ dni: string; code: string } | null>(fromQr);

  const { data, error, isFetching, refetch } = useQuery({
    queryKey: ["public-status", submitted],
    queryFn: () => api.get<PublicTicketStatus>("/public/ticket-status", { document_number: submitted!.dni, ticket_code: submitted!.code }),
    enabled: submitted !== null,
    retry: false,
    refetchInterval: (q) => (q.state.data && ["EN_ESPERA", "LLAMADO", "REGISTRADO", "EN_ATENCION"].includes(q.state.data.status) ? 30_000 : false),
  });

  const validDni = /^\d{8}$/.test(dni);
  const normalizedCode = code.trim().toUpperCase();
  const validCode = /^[A-Z]{1,3}-?\d{1,3}$/.test(normalizedCode);
  const submit = () => {
    const match = /^([A-Z]{1,3})-?(\d{1,3})$/.exec(normalizedCode);
    if (!validDni || !match) return;
    setSubmitted({ dni, code: `${match[1]}-${match[2]!.padStart(3, "0")}` });
  };

  const style = data ? statusStyle(data.status) : null;
  const called = data?.status === "LLAMADO";

  return (
    <div className="min-h-dvh bg-surface">
      <header className="bg-brand-900 px-5 pt-[max(1.25rem,env(safe-area-inset-top))] pb-16 text-white">
        <div className="mx-auto flex max-w-md items-center gap-3">
          <BrandMark />
          <div className="leading-tight">
            <p className="font-semibold">Tópico de Salud</p>
            <p className="text-xs text-white/65">Corte Superior de Justicia de Lima</p>
          </div>
        </div>
      </header>
      <main className="mx-auto -mt-10 max-w-md space-y-4 px-4 pb-10">
        <form
          className="card space-y-4 p-5"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <div>
            <h1 className="text-lg font-semibold tracking-tight">Consulte su turno</h1>
            <p className="text-sm text-ink-muted">Ingrese su DNI y el código de turno que le indicó el tópico.</p>
          </div>
          <Field label="DNI">
            <Input
              inputMode="numeric"
              autoComplete="off"
              maxLength={8}
              value={dni}
              onChange={(e) => setDni(e.target.value.replace(/\D/g, "").slice(0, 8))}
              className="tabular h-12 text-lg tracking-widest"
            />
          </Field>
          <Field label="Código de turno" hint="Por ejemplo: A-007">
            <Input
              autoComplete="off"
              autoCapitalize="characters"
              maxLength={7}
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase())}
              className="tabular h-12 text-lg tracking-widest uppercase"
            />
          </Field>
          <Button type="submit" size="lg" className="w-full" disabled={!validDni || !validCode} loading={isFetching && !data} icon={<Search className="size-4" />}>
            Consultar
          </Button>
        </form>

        {error && (
          <Callout tone={error instanceof ApiError && error.status === 429 ? "warning" : "danger"}>
            {error instanceof ApiError ? error.message : "No se pudo realizar la consulta."}
          </Callout>
        )}

        {data && style && (
          <section
            aria-live="polite"
            className={cn("card animate-slide-up overflow-hidden", called && "ring-2 ring-status-called")}
          >
            <div className={cn("px-5 py-6 text-center", style.bg)}>
              <p className="text-sm text-ink-muted">Hola, {data.worker_name}</p>
              <p className="tabular mt-1 text-6xl leading-none font-bold tracking-tight">{data.ticket_code}</p>
              <div className="mt-3 flex justify-center">
                <StatusBadge status={data.status} size="lg" />
              </div>
              <p className={cn("mx-auto mt-3 max-w-xs text-sm", called ? "font-semibold text-status-called" : "text-ink-muted")}>
                {MESSAGES[data.status] ?? data.status_description}
              </p>
            </div>
            {data.status === "EN_ESPERA" || data.status === "REGISTRADO" ? (
              <dl className="grid grid-cols-3 divide-x divide-line border-t border-line text-center">
                <div className="px-2 py-4">
                  <dt className="text-xs text-ink-soft">Posición</dt>
                  <dd className="tabular text-2xl font-semibold">{data.position ?? "—"}</dd>
                </div>
                <div className="px-2 py-4">
                  <dt className="text-xs text-ink-soft">Delante</dt>
                  <dd className="tabular text-2xl font-semibold">{data.people_ahead ?? "—"}</dd>
                </div>
                <div className="px-2 py-4">
                  <dt className="text-xs text-ink-soft">Hora aprox.</dt>
                  <dd className="tabular text-2xl font-semibold">{data.estimated_at ? fmt.time(data.estimated_at) : "—"}</dd>
                </div>
              </dl>
            ) : null}
            <div className="space-y-2 border-t border-line px-5 py-4 text-sm">
              <p className="flex items-start gap-2 text-ink-muted">
                <MapPin className="mt-0.5 size-4 shrink-0" aria-hidden />
                <span>
                  {data.site_name}
                  {data.location_note && <span className="block text-xs text-ink-soft">{data.location_note}</span>}
                </span>
              </p>
              <p className="flex items-center justify-between text-xs text-ink-soft">
                <span>
                  {fmt.date(data.service_date)} · registrado {fmt.time(data.registered_at)}
                </span>
                <button type="button" onClick={() => void refetch()} className="inline-flex items-center gap-1 font-medium text-brand-700">
                  <RefreshCw className={cn("size-3.5", isFetching && "animate-spin")} aria-hidden />
                  {fmt.time(data.updated_at)}
                </button>
              </p>
            </div>
          </section>
        )}

        <p className="flex items-start gap-2 px-1 text-xs leading-relaxed text-ink-soft">
          <ShieldCheck className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          Por su privacidad, esta consulta solo muestra información de su propio turno. La hora es referencial y se actualiza
          automáticamente.
        </p>
      </main>
    </div>
  );
}
