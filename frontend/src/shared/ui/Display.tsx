import { AlertTriangle, CheckCircle2, Info, OctagonAlert, type LucideIcon } from "lucide-react";
import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/shared/lib/cn";
import { statusStyle } from "@/shared/lib/status";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("card", className)} {...props} />;
}

export function CardHeader({
  title,
  description,
  actions,
  icon,
  className,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  icon?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex items-start justify-between gap-3 border-b border-line px-5 py-4", className)}>
      <div className="flex min-w-0 items-start gap-3">
        {icon && <div className="mt-0.5 text-ink-soft">{icon}</div>}
        <div className="min-w-0">
          <h2 className="text-[15px] font-semibold tracking-tight text-ink">{title}</h2>
          {description && <p className="mt-0.5 text-[13px] text-ink-soft">{description}</p>}
        </div>
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}

/** Insignia de estado: ícono + texto + color (accesible, no depende solo del color). */
export function StatusBadge({ status, size = "md", className }: { status: string; size?: "sm" | "md" | "lg"; className?: string }) {
  const s = statusStyle(status);
  const Icon = s.icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full font-medium whitespace-nowrap ring-1 ring-inset",
        s.bg,
        s.text,
        s.ring,
        size === "sm" && "px-2 py-0.5 text-xs",
        size === "md" && "px-2.5 py-1 text-[13px]",
        size === "lg" && "px-3 py-1.5 text-sm",
        status === "ANULADO" && "line-through decoration-1",
        className,
      )}
    >
      <Icon className={size === "sm" ? "size-3" : "size-3.5"} aria-hidden strokeWidth={2.25} />
      {s.label}
    </span>
  );
}

const TONES = {
  neutral: "bg-sunken text-ink-muted ring-line-strong",
  brand: "bg-brand-50 text-brand-800 ring-brand-200",
  success: "bg-status-done-bg text-status-done ring-status-done/20",
  warning: "bg-status-waiting-bg text-status-waiting ring-status-waiting/25",
  danger: "bg-status-noshow-bg text-status-noshow ring-status-noshow/20",
  info: "bg-status-called-bg text-status-called ring-status-called/20",
} as const;

export function Badge({
  tone = "neutral",
  className,
  children,
}: {
  tone?: keyof typeof TONES;
  className?: string;
  children: ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium whitespace-nowrap ring-1 ring-inset",
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

const CALLOUTS: Record<"info" | "success" | "warning" | "danger", { icon: LucideIcon; cls: string }> = {
  info: { icon: Info, cls: "border-status-called/20 bg-status-called-bg text-blue-950" },
  success: { icon: CheckCircle2, cls: "border-status-done/20 bg-status-done-bg text-emerald-950" },
  warning: { icon: AlertTriangle, cls: "border-status-waiting/25 bg-status-waiting-bg text-amber-950" },
  danger: { icon: OctagonAlert, cls: "border-status-noshow/20 bg-status-noshow-bg text-red-950" },
};

export function Callout({
  tone = "info",
  title,
  children,
  className,
  action,
}: {
  tone?: keyof typeof CALLOUTS;
  title?: ReactNode;
  children?: ReactNode;
  className?: string;
  action?: ReactNode;
}) {
  const { icon: Icon, cls } = CALLOUTS[tone];
  return (
    <div role={tone === "danger" ? "alert" : "status"} className={cn("flex gap-3 rounded-xl border px-4 py-3", cls, className)}>
      <Icon className="mt-0.5 size-[18px] shrink-0" aria-hidden />
      <div className="min-w-0 flex-1 text-sm">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className={cn("leading-relaxed", title && "mt-0.5 opacity-90")}>{children}</div>}
      </div>
      {action}
    </div>
  );
}

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="inline-flex h-5 min-w-5 items-center justify-center rounded border border-line-strong border-b-2 bg-panel px-1 font-sans text-[11px] font-semibold text-ink-muted">
      {children}
    </kbd>
  );
}

export function Spinner({ className, label = "Cargando" }: { className?: string; label?: string }) {
  return (
    <span role="status" aria-label={label} className={cn("inline-block size-5 animate-spin rounded-full border-2 border-line-strong border-t-brand-700", className)} />
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-lg bg-sunken", className)} aria-hidden />;
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: {
  icon: LucideIcon;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center justify-center px-6 py-12 text-center", className)}>
      <div className="grid size-12 place-items-center rounded-2xl bg-sunken text-ink-soft">
        <Icon className="size-6" aria-hidden />
      </div>
      <p className="mt-3 text-sm font-semibold text-ink">{title}</p>
      {description && <p className="mt-1 max-w-sm text-[13px] text-ink-soft">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

/** Tarjeta de indicador (DashboardCard). */
export function KpiCard({
  label,
  value,
  icon: Icon,
  tone = "neutral",
  hint,
  emphasis = false,
}: {
  label: string;
  value: ReactNode;
  icon: LucideIcon;
  tone?: "neutral" | "brand" | "waiting" | "called" | "inservice" | "done" | "danger";
  hint?: ReactNode;
  emphasis?: boolean;
}) {
  const tones = {
    neutral: "text-ink-muted bg-sunken",
    brand: "text-brand-700 bg-brand-50",
    waiting: "text-status-waiting bg-status-waiting-bg",
    called: "text-status-called bg-status-called-bg",
    inservice: "text-status-inservice bg-status-inservice-bg",
    done: "text-status-done bg-status-done-bg",
    danger: "text-status-noshow bg-status-noshow-bg",
  } as const;
  return (
    <div className={cn("card flex items-center gap-3 px-4 py-3.5", emphasis && "border-brand-200 bg-brand-50/40")}>
      <div className={cn("grid size-10 shrink-0 place-items-center rounded-xl", tones[tone])}>
        <Icon className="size-5" aria-hidden />
      </div>
      <div className="min-w-0">
        <p className="line-clamp-2 text-xs leading-tight font-medium tracking-wide text-ink-soft uppercase">{label}</p>
        <p className="tabular text-2xl leading-tight font-semibold tracking-tight text-ink">{value}</p>
        {hint && <p className="line-clamp-2 text-xs text-ink-soft">{hint}</p>}
      </div>
    </div>
  );
}

export function PageHeader({
  title,
  description,
  actions,
  eyebrow,
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  eyebrow?: ReactNode;
}) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {eyebrow && <p className="mb-1 text-xs font-semibold tracking-[0.08em] text-brand-700 uppercase">{eyebrow}</p>}
        <h1 className="text-2xl font-semibold tracking-tight text-ink">{title}</h1>
        {description && <p className="mt-1 max-w-2xl text-sm text-ink-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

export function DefinitionList({ items, className }: { items: [ReactNode, ReactNode][]; className?: string }) {
  return (
    <dl className={cn("grid grid-cols-[minmax(7rem,auto)_1fr] gap-x-4 gap-y-2.5 text-sm", className)}>
      {items.map(([term, value], index) => (
        <div key={index} className="contents">
          <dt className="text-ink-soft">{term}</dt>
          <dd className="min-w-0 text-ink">{value}</dd>
        </div>
      ))}
    </dl>
  );
}
