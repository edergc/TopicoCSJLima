import { Contrast, Minus, Plus, Type } from "lucide-react";

import { cn } from "@/shared/lib/cn";
import { Menu, MenuContent, MenuLabel, MenuSeparator, MenuTrigger } from "@/shared/ui";

import { SCALES, setA11y, useA11y } from "./preferences";

/** Botón de accesibilidad: tamaño de letra (A− / A+) y alto contraste. Disponible en toda la interfaz. */
export function AccessibilityMenu({ tone = "light", className }: { tone?: "light" | "dark"; className?: string }) {
  const prefs = useA11y();
  const index = SCALES.indexOf(prefs.scale as (typeof SCALES)[number]);
  const step = (delta: number) => setA11y({ scale: SCALES[Math.min(Math.max(index + delta, 0), SCALES.length - 1)] });

  return (
    <Menu>
      <MenuTrigger asChild>
        <button
          type="button"
          aria-label="Accesibilidad: tamaño de letra y contraste"
          title="Accesibilidad"
          className={cn(
            "grid size-9 place-items-center rounded-lg ring-1 transition",
            tone === "dark"
              ? "text-white/80 ring-white/20 hover:bg-white/10 hover:text-white"
              : "bg-panel text-ink-muted ring-line hover:text-ink hover:ring-line-strong",
            className,
          )}
        >
          <Type className="size-4" aria-hidden />
        </button>
      </MenuTrigger>
      <MenuContent align="end" className="w-64">
        <MenuLabel>Tamaño de letra</MenuLabel>
        <div className="flex items-center gap-2 px-2 pb-2">
          <button
            type="button"
            onClick={() => step(-1)}
            disabled={index <= 0}
            aria-label="Reducir tamaño de letra"
            className="grid size-9 place-items-center rounded-lg ring-1 ring-line hover:bg-sunken disabled:opacity-40"
          >
            <Minus className="size-4" />
          </button>
          <span className="tabular flex-1 text-center text-sm font-semibold" aria-live="polite">
            {Math.round(prefs.scale * 100)} %
          </span>
          <button
            type="button"
            onClick={() => step(1)}
            disabled={index >= SCALES.length - 1}
            aria-label="Aumentar tamaño de letra"
            className="grid size-9 place-items-center rounded-lg ring-1 ring-line hover:bg-sunken disabled:opacity-40"
          >
            <Plus className="size-4" />
          </button>
        </div>
        <MenuSeparator />
        <button
          type="button"
          role="switch"
          aria-checked={prefs.contrast}
          onClick={() => setA11y({ contrast: !prefs.contrast })}
          className="flex w-full items-center gap-3 rounded-md px-2 py-2 text-left text-sm hover:bg-sunken"
        >
          <Contrast className="size-4" aria-hidden />
          <span className="flex-1">Alto contraste</span>
          <span
            className={cn(
              "relative h-5 w-9 rounded-full transition",
              prefs.contrast ? "bg-brand-700" : "bg-line-strong",
            )}
            aria-hidden
          >
            <span className={cn("absolute top-0.5 size-4 rounded-full bg-white transition", prefs.contrast ? "left-4.5" : "left-0.5")} />
          </span>
        </button>
        {(prefs.scale !== 1 || prefs.contrast) && (
          <button type="button" onClick={() => setA11y({ scale: 1, contrast: false })} className="mt-1 w-full px-2 py-1.5 text-left text-[0.8125rem] text-brand-700 hover:underline">
            Restablecer
          </button>
        )}
        <p className="px-2 pt-1 pb-1 text-[0.6875rem] text-ink-soft">Se recuerda en este equipo.</p>
      </MenuContent>
    </Menu>
  );
}
