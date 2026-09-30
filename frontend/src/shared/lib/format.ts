/**
 * Formateo de fechas y horas en la zona institucional (America/Lima), independiente
 * de la zona horaria configurada en el equipo del usuario.
 */
export const TIME_ZONE = "America/Lima";
const LOCALE = "es-PE";

const timeFmt = new Intl.DateTimeFormat(LOCALE, { timeZone: TIME_ZONE, hour: "2-digit", minute: "2-digit", hour12: false });
const dateFmt = new Intl.DateTimeFormat(LOCALE, { timeZone: TIME_ZONE, day: "2-digit", month: "2-digit", year: "numeric" });
const dateTimeFmt = new Intl.DateTimeFormat(LOCALE, {
  timeZone: TIME_ZONE,
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});
const longDateFmt = new Intl.DateTimeFormat(LOCALE, { timeZone: TIME_ZONE, weekday: "long", day: "numeric", month: "long" });
const isoDateFmt = new Intl.DateTimeFormat("en-CA", { timeZone: TIME_ZONE, year: "numeric", month: "2-digit", day: "2-digit" });

type DateLike = string | number | Date | null | undefined;

function toDate(value: DateLike): Date | null {
  if (value === null || value === undefined || value === "") return null;
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** "YYYY-MM-DD" (fecha de negocio) → Date al mediodía UTC, evita corrimientos de día. */
function fromIsoDate(value: string): Date {
  return new Date(`${value}T12:00:00Z`);
}

export const fmt = {
  time: (value: DateLike) => {
    const d = toDate(value);
    return d ? timeFmt.format(d) : "—";
  },
  dateTime: (value: DateLike) => {
    const d = toDate(value);
    return d ? dateTimeFmt.format(d) : "—";
  },
  /** Fecha de negocio "YYYY-MM-DD" → "29/09/2026". */
  date: (value: string | null | undefined) => (value ? dateFmt.format(fromIsoDate(value)) : "—"),
  longDate: (value: string) => {
    const text = longDateFmt.format(fromIsoDate(value));
    return text.charAt(0).toUpperCase() + text.slice(1);
  },
  number: (value: number | null | undefined, digits = 0) =>
    value === null || value === undefined
      ? "—"
      : value.toLocaleString(LOCALE, { minimumFractionDigits: digits, maximumFractionDigits: digits }),
};

/** Fecha de hoy en Lima como "YYYY-MM-DD". */
export function todayIso(now = new Date()): string {
  return isoDateFmt.format(now);
}

export function addDaysIso(iso: string, days: number): string {
  const d = fromIsoDate(iso);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

/** Minutos transcurridos desde un instante (redondeo hacia abajo). */
export function minutesSince(value: DateLike, now = Date.now()): number | null {
  const d = toDate(value);
  return d ? Math.max(0, Math.floor((now - d.getTime()) / 60_000)) : null;
}

/** "mm:ss" de una cuenta regresiva hasta un instante (null si ya pasó). */
export function countdown(until: DateLike, now = Date.now()): string | null {
  const d = toDate(until);
  if (!d) return null;
  const seconds = Math.ceil((d.getTime() - now) / 1000);
  if (seconds <= 0) return null;
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

export function formatDuration(minutes: number | null): string {
  if (minutes === null) return "—";
  if (minutes < 60) return `${minutes} min`;
  return `${Math.floor(minutes / 60)} h ${minutes % 60} min`;
}
