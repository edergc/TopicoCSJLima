import { CheckCircle2, LockKeyhole } from "lucide-react";
import type { ReactNode } from "react";

import { BrandMark } from "@/app/layout/BrandMark";
import { AccessibilityMenu } from "@/shared/a11y/AccessibilityMenu";
import { logoUrl, useBranding, useBrandingReady } from "@/shared/branding/branding";
import { cn } from "@/shared/lib/cn";

const HIGHLIGHTS = [
  "Turnos en orden de registro y cola en tiempo real",
  "Operación por sede con trazabilidad completa",
  "Datos administrativos protegidos, sin información clínica",
];

/** Placa institucional: logo oficial sobre fondo blanco (el logo tiene texto oscuro y fondo transparente). */
function InstitutionPlate({ compact = false }: { compact?: boolean }) {
  const branding = useBranding();
  const ready = useBrandingReady();
  const logo = logoUrl(branding);
  return (
    <div
      className={cn(
        "inline-flex w-fit items-center gap-4 self-start rounded-2xl bg-white text-ink shadow-[0_10px_30px_-12px_rgb(0_0_0/0.45)] ring-1 ring-black/5",
        compact ? "gap-3 px-3 py-2.5" : "px-5 py-4",
      )}
    >
      {!ready ? (
        <span className={cn("rounded-xl bg-sunken", compact ? "size-11" : "size-[4.5rem]")} aria-hidden />
      ) : logo ? (
        <img src={logo} alt="" className={cn("w-auto object-contain", compact ? "h-11" : "h-[4.5rem]")} />
      ) : (
        <BrandMark tone="dark" className={compact ? "size-10" : "size-14"} />
      )}
      <span className="h-10 w-px bg-line" aria-hidden />
      <span className="leading-tight">
        <span className="block text-[0.6875rem] font-semibold tracking-[0.14em] text-brand-700 uppercase">{branding.org_name}</span>
        <span className={cn("block font-semibold text-ink", compact ? "text-sm" : "text-base")}>{branding.institution_name}</span>
      </span>
    </div>
  );
}

/** Cruz de servicio de salud, como marca de agua del panel institucional. */
function CrossWatermark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden>
      <path fill="currentColor" d="M9.5 3h5v6.5H21v5h-6.5V21h-5v-6.5H3v-5h6.5z" />
    </svg>
  );
}

/** Marco de las pantallas sin sesión del personal: ingreso y recuperación de contraseña. */
export function AuthLayout({ title, subtitle, children }: { title: string; subtitle?: ReactNode; children: ReactNode }) {
  const branding = useBranding();
  const year = new Date().getFullYear();

  return (
    <div className="grid min-h-dvh bg-surface lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
      {/* Panel institucional (escritorio) */}
      <section className="relative hidden overflow-hidden bg-brand-900 text-white lg:flex lg:flex-col">
        <div
          className="absolute inset-0 bg-[radial-gradient(90%_70%_at_0%_0%,var(--color-brand-600)_0%,transparent_62%),radial-gradient(70%_60%_at_100%_100%,color-mix(in_oklab,var(--color-brand-900)_55%,black)_0%,transparent_70%)]"
          aria-hidden
        />
        <CrossWatermark className="absolute -right-24 -bottom-28 size-[34rem] rotate-12 text-white/[0.035]" />
        <div className="absolute inset-y-0 right-0 w-px bg-gradient-to-b from-transparent via-white/15 to-transparent" aria-hidden />

        <div className="relative flex flex-1 flex-col px-14 py-12">
          <InstitutionPlate />

          <div className="mt-auto max-w-xl">
            <span className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-medium tracking-[0.08em] text-white/85 uppercase ring-1 ring-white/15">
              <span className="size-1.5 rounded-full bg-emerald-400" aria-hidden />
              Tópico de Salud · Bienestar del trabajador
            </span>
            <h1 className="mt-5 text-[2.75rem] leading-[1.08] font-semibold tracking-tight text-balance">{branding.system_name}</h1>
            <p className="mt-5 max-w-lg text-base leading-relaxed text-white/72">
              Registro, cola y seguimiento de las atenciones de los tópicos de salud de la institución, con trazabilidad completa y
              protección de los datos del personal.
            </p>
            <ul className="mt-9 divide-y divide-white/10 border-y border-white/10">
              {HIGHLIGHTS.map((text) => (
                <li key={text} className="flex items-center gap-3 py-3 text-sm text-white/85">
                  <CheckCircle2 className="size-4 shrink-0 text-white/60" aria-hidden />
                  {text}
                </li>
              ))}
            </ul>
          </div>

          <div className="mt-12 flex flex-wrap items-center justify-between gap-3 text-xs text-white/45">
            <span>
              © {year} {branding.institution_name}
            </span>
            <span>{branding.org_name}</span>
          </div>
        </div>
      </section>

      {/* Acceso */}
      <section className="relative flex flex-col">
        {/* Cabecera institucional (celular y tablet) */}
        <div className="relative overflow-hidden bg-brand-900 px-5 pt-5 pb-16 text-white lg:hidden">
          <div className="absolute inset-0 bg-[radial-gradient(90%_80%_at_0%_0%,var(--color-brand-600)_0%,transparent_65%)]" aria-hidden />
          <CrossWatermark className="absolute -right-10 -bottom-16 size-48 rotate-12 text-white/[0.06]" />
          <div className="relative flex items-start justify-between gap-3">
            <InstitutionPlate compact />
            <AccessibilityMenu tone="dark" />
          </div>
        </div>

        <div className="hidden justify-end px-8 pt-6 lg:flex">
          <AccessibilityMenu />
        </div>

        <div className="relative mx-auto -mt-10 flex w-full max-w-[27rem] flex-1 flex-col px-4 pb-8 lg:mt-0 lg:justify-center lg:px-0 lg:py-8">
          <div className="rounded-2xl border border-line bg-panel p-6 shadow-[0_24px_48px_-24px_rgb(28_25_23/0.28)] sm:p-8">
            <p className="text-xs font-semibold tracking-[0.12em] text-brand-700 uppercase">Acceso del personal</p>
            <h2 className="mt-1.5 text-2xl font-semibold tracking-tight">{title}</h2>
            {subtitle && <p className="mt-1.5 text-sm leading-relaxed text-ink-muted">{subtitle}</p>}
            <div className="mt-7">{children}</div>
          </div>
          <p className="mt-5 flex items-start gap-2 px-1 text-xs leading-relaxed text-ink-soft">
            <LockKeyhole className="mt-0.5 size-3.5 shrink-0" aria-hidden />
            Uso exclusivo del personal autorizado. Todas las acciones quedan registradas en la auditoría del sistema.
          </p>
          <p className="mt-6 text-center text-xs text-ink-faint lg:hidden">
            © {year} {branding.institution_name}
          </p>
        </div>
      </section>
    </div>
  );
}
