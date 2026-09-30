import { cn } from "@/shared/lib/cn";

/**
 * Marca del sistema (cruz de servicio de salud sobre granate).
 * Reemplazable por el logotipo oficial cuando se disponga del manual de identidad.
 */
export function BrandMark({ className, tone = "light" }: { className?: string; tone?: "light" | "dark" }) {
  return (
    <span
      className={cn(
        "grid size-10 shrink-0 place-items-center rounded-xl",
        tone === "light" ? "bg-white/12 ring-1 ring-white/20" : "bg-brand-700",
        className,
      )}
      aria-hidden
    >
      <svg viewBox="0 0 24 24" className="size-5 fill-white">
        <path d="M9.5 3h5v6.5H21v5h-6.5V21h-5v-6.5H3v-5h6.5z" />
      </svg>
    </span>
  );
}
