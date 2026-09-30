import { useLayoutEffect, useRef, useState } from "react";

/**
 * Columnas (apiladas o simples) en SVG, sin dependencias.
 *
 * Especificaciones de visualización (validadas):
 *  - columnas <= 24px, extremo superior redondeado 4px, base recta en el eje;
 *  - 2px de separación (color de superficie) entre segmentos apilados;
 *  - grilla/ejes en línea fina recesiva; texto siempre en tonos de texto, nunca en el color de la serie;
 *  - tooltip por columna (área de interacción = toda la banda, más grande que la marca);
 *  - leyenda para >= 2 series (la identidad nunca depende solo del color).
 */
export interface ChartSeries {
  key: string;
  label: string;
  color: string;
}

export interface ColumnDatum {
  label: string;
  /** Etiqueta larga para el tooltip. */
  title?: string;
  values: Record<string, number>;
  /** Marca de referencia (p. ej., capacidad del día). */
  reference?: number;
}

interface Props {
  data: ColumnDatum[];
  series: ChartSeries[];
  height?: number;
  referenceLabel?: string;
  ariaLabel: string;
}

const PAD = { top: 12, right: 8, bottom: 28, left: 36 };
const GAP = 2;
const RADIUS = 4;

function niceMax(value: number): number {
  if (value <= 5) return 5;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const step = [1, 2, 2.5, 5, 10].find((s) => (s * magnitude * 4) >= value)! * magnitude;
  return Math.ceil(value / step) * step;
}

/** Rectángulo con esquinas superiores redondeadas (base recta). */
function topRounded(x: number, y: number, w: number, h: number, r: number): string {
  const rr = Math.min(r, h, w / 2);
  return `M${x},${y + h}V${y + rr}Q${x},${y} ${x + rr},${y}H${x + w - rr}Q${x + w},${y} ${x + w},${y + rr}V${y + h}Z`;
}

export function ColumnChart({ data, series, height = 240, referenceLabel, ariaLabel }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(640);
  const [hover, setHover] = useState<number | null>(null);

  useLayoutEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => entry && setWidth(Math.max(280, entry.contentRect.width)));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const totals = data.map((d) => series.reduce((sum, s) => sum + (d.values[s.key] ?? 0), 0));
  const max = niceMax(Math.max(1, ...totals, ...data.map((d) => d.reference ?? 0)));
  const plotW = width - PAD.left - PAD.right;
  const plotH = height - PAD.top - PAD.bottom;
  const band = plotW / Math.max(1, data.length);
  const barW = Math.max(4, Math.min(24, band * 0.6));
  const y = (v: number) => PAD.top + plotH - (v / max) * plotH;
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => Math.round(max * t));
  const labelEvery = Math.max(1, Math.ceil(data.length / Math.floor(plotW / 44)));
  const hovered = hover !== null ? data[hover] : undefined;

  return (
    <div ref={containerRef} className="relative">
      {series.length > 1 && (
        <ul className="mb-3 flex flex-wrap gap-x-4 gap-y-1 text-[13px] text-ink-muted" aria-label="Leyenda">
          {series.map((s) => (
            <li key={s.key} className="flex items-center gap-1.5">
              <span className="size-2.5 rounded-sm" style={{ background: s.color }} aria-hidden />
              {s.label}
            </li>
          ))}
          {referenceLabel && (
            <li className="flex items-center gap-1.5">
              <span className="h-0.5 w-3 bg-ink" aria-hidden />
              {referenceLabel}
            </li>
          )}
        </ul>
      )}
      <svg width={width} height={height} role="img" aria-label={ariaLabel} className="block overflow-visible" onMouseLeave={() => setHover(null)}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={PAD.left} x2={width - PAD.right} y1={y(t)} y2={y(t)} stroke="var(--color-line)" strokeWidth={1} />
            <text x={PAD.left - 8} y={y(t)} dy="0.32em" textAnchor="end" className="fill-ink-soft text-[11px] tabular">
              {t.toLocaleString("es-PE")}
            </text>
          </g>
        ))}
        {data.map((d, i) => {
          const cx = PAD.left + band * i + band / 2;
          const x = cx - barW / 2;
          let acc = 0;
          const visible = series.filter((s) => (d.values[s.key] ?? 0) > 0);
          return (
            <g key={i}>
              {hover === i && <rect x={PAD.left + band * i} y={PAD.top} width={band} height={plotH} fill="var(--color-sunken)" opacity={0.6} />}
              {visible.map((s, j) => {
                const v = d.values[s.key] ?? 0;
                const y0 = y(acc);
                acc += v;
                const y1 = y(acc);
                const isTop = j === visible.length - 1;
                const h = Math.max(0, y0 - y1 - (isTop ? 0 : GAP));
                return isTop ? (
                  <path key={s.key} d={topRounded(x, y1, barW, h, RADIUS)} fill={s.color} />
                ) : (
                  <rect key={s.key} x={x} y={y1 + GAP} width={barW} height={h} fill={s.color} />
                );
              })}
              {d.reference !== undefined && d.reference > 0 && (
                <line x1={x - 4} x2={x + barW + 4} y1={y(d.reference)} y2={y(d.reference)} stroke="var(--color-ink)" strokeWidth={2} strokeLinecap="round" />
              )}
              {i % labelEvery === 0 && (
                <text x={cx} y={height - 8} textAnchor="middle" className="fill-ink-soft text-[11px] tabular">
                  {d.label}
                </text>
              )}
              <rect
                x={PAD.left + band * i}
                y={PAD.top}
                width={band}
                height={plotH}
                fill="transparent"
                onMouseEnter={() => setHover(i)}
                onFocus={() => setHover(i)}
                onBlur={() => setHover(null)}
                tabIndex={0}
                aria-label={`${d.title ?? d.label}: ${series.map((s) => `${s.label} ${d.values[s.key] ?? 0}`).join(", ")}`}
              />
            </g>
          );
        })}
        <line x1={PAD.left} x2={width - PAD.right} y1={y(0)} y2={y(0)} stroke="var(--color-line-strong)" strokeWidth={1} />
      </svg>
      {hovered && hover !== null && (
        <div
          role="tooltip"
          className="pointer-events-none absolute z-10 min-w-40 rounded-lg border border-line bg-panel px-3 py-2 text-[13px] shadow-[var(--shadow-raised)]"
          style={{
            left: Math.min(Math.max(PAD.left + band * hover + band / 2 - 80, 0), width - 170),
            top: 0,
          }}
        >
          <p className="mb-1 font-semibold text-ink">{hovered.title ?? hovered.label}</p>
          {series.map((s) => (
            <p key={s.key} className="flex items-center justify-between gap-4 text-ink-muted">
              <span className="flex items-center gap-1.5">
                <span className="size-2 rounded-sm" style={{ background: s.color }} aria-hidden />
                {s.label}
              </span>
              <span className="tabular font-medium text-ink">{hovered.values[s.key] ?? 0}</span>
            </p>
          ))}
          {hovered.reference !== undefined && referenceLabel && (
            <p className="mt-1 flex justify-between gap-4 border-t border-line pt-1 text-ink-muted">
              {referenceLabel} <span className="tabular font-medium text-ink">{hovered.reference}</span>
            </p>
          )}
        </div>
      )}
    </div>
  );
}
