import { useMutation, useQuery } from "@tanstack/react-query";
import { CheckCircle2, ShieldCheck, Star } from "lucide-react";
import { useState } from "react";

import { AccessibilityMenu } from "@/shared/a11y/AccessibilityMenu";
import { useBranding } from "@/shared/branding/branding";
import { BrandMark } from "@/app/layout/BrandMark";
import { ApiError, api } from "@/shared/api/client";
import type { RatingLookup } from "@/shared/api/types";
import { cn } from "@/shared/lib/cn";
import { fmt } from "@/shared/lib/format";
import { useDocumentTitle } from "@/shared/lib/hooks";
import { Button, Callout, Field, Skeleton, Textarea } from "@/shared/ui";

const LABELS = ["", "Muy malo", "Malo", "Regular", "Bueno", "Excelente"];

function readToken(): string {
  const token = window.location.hash.slice(1);
  if (token) window.history.replaceState(null, "", window.location.pathname); // el enlace no queda visible
  return token;
}

/** Calificación anónima de la atención (enlace recibido por correo). Solo trato y espera: nada de salud. */
export default function RatingPage() {
  const branding = useBranding();
  useDocumentTitle("Califique su atención");
  const [token] = useState(readToken);
  const [score, setScore] = useState(0);
  const [waitScore, setWaitScore] = useState(0);
  const [comment, setComment] = useState("");

  const lookup = useQuery({
    queryKey: ["rating", token],
    queryFn: () => api.post<RatingLookup>("/public/rating/lookup", { token }, { skipRefresh: true }),
    enabled: token.length >= 16,
    retry: false,
  });
  const submit = useMutation({
    mutationFn: () =>
      api.post("/public/rating", { token, score, wait_score: waitScore || null, comment: comment.trim() || null }, { skipRefresh: true }),
  });

  const info = lookup.data;
  const done = submit.isSuccess || info?.submitted;

  return (
    <div className="min-h-dvh bg-surface">
      <header className="bg-brand-900 px-5 pt-[max(1.25rem,env(safe-area-inset-top))] pb-16 text-white">
        <div className="mx-auto flex max-w-md items-center gap-3">
          <BrandMark />
          <div className="leading-tight">
            <p className="font-semibold">Tópico de Salud</p>
            <p className="text-xs text-white/65">{branding.institution_name}</p>
          </div>
          <AccessibilityMenu tone="dark" className="ml-auto" />
        </div>
      </header>
      <main className="mx-auto -mt-10 max-w-md space-y-4 px-4 pb-10">
        <div className="card p-5">
          {token.length < 16 ? (
            <Callout tone="danger">El enlace no es válido. Ábralo directamente desde el correo recibido.</Callout>
          ) : lookup.isLoading ? (
            <Skeleton className="h-48" />
          ) : lookup.error ? (
            <Callout tone="danger">{lookup.error instanceof ApiError ? lookup.error.message : "No se pudo abrir la encuesta."}</Callout>
          ) : done ? (
            <div className="py-6 text-center">
              <CheckCircle2 className="mx-auto size-14 text-success" aria-hidden />
              <h1 className="mt-3 text-xl font-semibold">¡Gracias por su opinión!</h1>
              <p className="mt-1 text-sm text-ink-muted">Nos ayuda a mejorar la atención del Tópico de Salud.</p>
            </div>
          ) : info?.expired ? (
            <Callout tone="warning">Este enlace venció. ¡Gracias de todas formas!</Callout>
          ) : (
            <form
              className="space-y-5"
              onSubmit={(e) => {
                e.preventDefault();
                if (score) submit.mutate();
              }}
            >
              <div>
                <h1 className="text-lg font-semibold tracking-tight">¿Cómo fue su atención?</h1>
                <p className="text-sm text-ink-muted">
                  {info?.site_name} · {info ? fmt.date(info.service_date) : ""}
                </p>
              </div>
              <Stars label="Trato recibido" value={score} onChange={setScore} />
              <Stars label="Tiempo de espera" value={waitScore} onChange={setWaitScore} optional />
              <Field label="Comentario (opcional)" hint="No incluya datos personales ni de salud.">
                <Textarea rows={3} maxLength={500} value={comment} onChange={(e) => setComment(e.target.value)} />
              </Field>
              {submit.error && (
                <Callout tone="danger">{submit.error instanceof ApiError ? submit.error.message : "No se pudo enviar."}</Callout>
              )}
              <Button type="submit" size="lg" className="w-full" disabled={!score} loading={submit.isPending}>
                Enviar calificación
              </Button>
            </form>
          )}
        </div>
        <p className="flex items-start gap-2 px-1 text-xs text-ink-soft">
          <ShieldCheck className="mt-0.5 size-4 shrink-0" aria-hidden />
          Su respuesta es anónima: los reportes solo muestran promedios y comentarios sin nombre.
        </p>
      </main>
    </div>
  );
}

function Stars({ label, value, onChange, optional }: { label: string; value: number; onChange: (v: number) => void; optional?: boolean }) {
  return (
    <fieldset>
      <legend className="mb-2 text-[0.8125rem] font-medium text-ink">
        {label}
        {optional && <span className="font-normal text-ink-soft"> (opcional)</span>}
      </legend>
      <div className="flex items-center gap-1" role="radiogroup" aria-label={label}>
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            role="radio"
            aria-checked={value === n}
            aria-label={`${n} — ${LABELS[n]}`}
            onClick={() => onChange(n)}
            className="rounded-lg p-1 transition hover:scale-110 focus-visible:outline-2"
          >
            <Star className={cn("size-9", n <= value ? "fill-amber-400 text-amber-400" : "text-line-strong")} aria-hidden />
          </button>
        ))}
        <span className="ml-2 text-sm text-ink-muted">{LABELS[value]}</span>
      </div>
    </fieldset>
  );
}
