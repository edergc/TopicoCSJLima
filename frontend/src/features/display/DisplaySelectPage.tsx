import { useQuery } from "@tanstack/react-query";
import { ChevronRight, MonitorPlay } from "lucide-react";
import { Link } from "react-router-dom";

import { BrandMark } from "@/app/layout/BrandMark";
import { ApiError, api } from "@/shared/api/client";
import type { DisplaySite } from "@/shared/api/types";
import { useDocumentTitle } from "@/shared/lib/hooks";
import { Callout, Skeleton } from "@/shared/ui";

/** Elección de la sede cuya pantalla de turnos se mostrará en la TV de la sala de espera. */
export default function DisplaySelectPage() {
  useDocumentTitle("Pantalla de turnos");
  const { data, error, isLoading } = useQuery({
    queryKey: ["display-sites"],
    queryFn: () => api.get<DisplaySite[]>("/public/display/sites"),
    retry: false,
  });

  return (
    <div className="min-h-dvh bg-surface">
      <header className="bg-brand-900 px-5 pt-6 pb-20 text-white">
        <div className="mx-auto flex max-w-2xl items-center gap-3">
          <BrandMark />
          <div className="leading-tight">
            <p className="font-semibold">Pantalla de turnos</p>
            <p className="text-xs text-white/65">Tópico de Salud · Corte Superior de Justicia de Lima</p>
          </div>
        </div>
      </header>
      <main className="mx-auto -mt-12 max-w-2xl space-y-4 px-4 pb-10">
        <div className="card p-6">
          <h1 className="text-lg font-semibold tracking-tight">¿Qué sede mostrará esta pantalla?</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Abra esta página en la TV o monitor de la sala de espera. Guarde la dirección de la sede como favorito o página de inicio del
            navegador.
          </p>
          <div className="mt-5 grid gap-3">
            {isLoading && <Skeleton className="h-20" />}
            {error && <Callout tone="danger">{error instanceof ApiError ? error.message : "No se pudo cargar la lista de sedes."}</Callout>}
            {data?.map((site) => (
              <Link
                key={site.code}
                to={`/pantalla/${site.code.toLowerCase()}`}
                className="group flex items-center gap-4 rounded-xl border border-line bg-panel p-4 transition hover:border-brand-300 hover:shadow-[var(--shadow-raised)]"
              >
                <span className="grid size-12 place-items-center rounded-xl bg-brand-50 text-brand-700">
                  <MonitorPlay className="size-6" aria-hidden />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block font-semibold text-ink">{site.name}</span>
                  <span className="block truncate font-mono text-xs text-ink-soft">
                    {window.location.host}/pantalla/{site.code.toLowerCase()}
                  </span>
                </span>
                <ChevronRight className="size-5 text-ink-faint transition group-hover:translate-x-0.5 group-hover:text-brand-700" aria-hidden />
              </Link>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
