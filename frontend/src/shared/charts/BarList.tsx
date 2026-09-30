/**
 * Barras horizontales de una sola serie (ranking). Valor al final de cada barra;
 * sin leyenda (el título nombra la serie). Barras <= 24px de alto, extremo redondeado.
 */
export function BarList({
  items,
  color,
  ariaLabel,
  formatValue = (v) => v.toLocaleString("es-PE"),
}: {
  items: { label: string; value: number }[];
  color: string;
  ariaLabel: string;
  formatValue?: (value: number) => string;
}) {
  const max = Math.max(1, ...items.map((i) => i.value));
  return (
    <ul className="space-y-2.5" aria-label={ariaLabel}>
      {items.map((item) => (
        <li key={item.label} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 text-[13px]">
          <span className="truncate text-ink-muted" title={item.label}>
            {item.label}
          </span>
          <span className="tabular font-medium text-ink">{formatValue(item.value)}</span>
          <span className="col-span-2 h-2.5 rounded-r bg-sunken">
            <span
              className="block h-full rounded-r"
              style={{ width: `${Math.max(2, (item.value / max) * 100)}%`, background: color }}
              aria-hidden
            />
          </span>
        </li>
      ))}
    </ul>
  );
}
