import { ChevronLeft, ChevronRight, Inbox, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/shared/lib/cn";

import { Button } from "./Button";
import { EmptyState, Skeleton } from "./Display";

export interface Column<T> {
  key: string;
  header: ReactNode;
  cell: (row: T) => ReactNode;
  className?: string;
  headerClassName?: string;
  /** Oculta la columna en pantallas pequeñas. */
  hideOnMobile?: boolean;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[] | undefined;
  rowKey: (row: T) => string | number;
  loading?: boolean;
  onRowClick?: (row: T) => void;
  empty?: { icon?: LucideIcon; title: string; description?: ReactNode };
  caption?: string;
  className?: string;
}

export function DataTable<T>({ columns, rows, rowKey, loading, onRowClick, empty, caption, className }: DataTableProps<T>) {
  return (
    <div className={cn("overflow-x-auto", className)}>
      <table className="w-full border-separate border-spacing-0 text-sm">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                className={cn(
                  "sticky top-0 z-[1] border-b border-line bg-surface/95 px-4 py-2.5 text-left text-xs font-semibold tracking-wide text-ink-soft uppercase backdrop-blur",
                  column.hideOnMobile && "hidden md:table-cell",
                  column.headerClassName,
                )}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {loading &&
            Array.from({ length: 5 }, (_, i) => (
              <tr key={`sk-${i}`}>
                {columns.map((column) => (
                  <td key={column.key} className={cn("border-b border-line px-4 py-3", column.hideOnMobile && "hidden md:table-cell")}>
                    <Skeleton className="h-4 w-3/4" />
                  </td>
                ))}
              </tr>
            ))}
          {!loading &&
            rows?.map((row) => (
              <tr
                key={rowKey(row)}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                onKeyDown={onRowClick ? (e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), onRowClick(row)) : undefined}
                tabIndex={onRowClick ? 0 : undefined}
                className={cn("group", onRowClick && "cursor-pointer hover:bg-surface focus-visible:bg-brand-50/50 focus-visible:outline-none")}
              >
                {columns.map((column) => (
                  <td
                    key={column.key}
                    className={cn("border-b border-line px-4 py-3 align-middle", column.hideOnMobile && "hidden md:table-cell", column.className)}
                  >
                    {column.cell(row)}
                  </td>
                ))}
              </tr>
            ))}
        </tbody>
      </table>
      {!loading && rows?.length === 0 && (
        <EmptyState icon={empty?.icon ?? Inbox} title={empty?.title ?? "Sin resultados"} description={empty?.description} />
      )}
    </div>
  );
}

export function Pagination({
  page,
  size,
  total,
  onPageChange,
}: {
  page: number;
  size: number;
  total: number;
  onPageChange: (page: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / size));
  const from = total === 0 ? 0 : (page - 1) * size + 1;
  const to = Math.min(page * size, total);
  return (
    <nav className="flex items-center justify-between gap-3 border-t border-line px-4 py-3 text-[0.8125rem] text-ink-soft" aria-label="Paginación">
      <p className="tabular">
        {from}–{to} de {total.toLocaleString("es-PE")}
      </p>
      <div className="flex items-center gap-1">
        <Button variant="ghost" size="sm" onClick={() => onPageChange(page - 1)} disabled={page <= 1} icon={<ChevronLeft className="size-4" />}>
          Anterior
        </Button>
        <span className="tabular px-2">
          {page} / {pages}
        </span>
        <Button variant="ghost" size="sm" onClick={() => onPageChange(page + 1)} disabled={page >= pages} trailing={<ChevronRight className="size-4" />}>
          Siguiente
        </Button>
      </div>
    </nav>
  );
}
