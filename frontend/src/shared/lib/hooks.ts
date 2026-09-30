import { useEffect, useRef, useState } from "react";

import { onServerTimeChange, serverNow } from "./serverTime";

/** Hora del servidor, actualizada periódicamente (relojes, cronómetros, cuentas regresivas). */
export function useNow(intervalMs = 1000): number {
  const [now, setNow] = useState(() => serverNow());
  useEffect(() => {
    const tick = () => setNow(serverNow());
    const id = window.setInterval(tick, intervalMs);
    const unsubscribe = onServerTimeChange(tick);
    return () => {
      window.clearInterval(id);
      unsubscribe();
    };
  }, [intervalMs]);
  return now;
}

/** Atajo de teclado global (p. ej., F2, F4). Se ignora mientras hay un diálogo abierto. */
export function useHotkey(key: string, handler: (event: KeyboardEvent) => void, enabled = true): void {
  const handlerRef = useRef(handler);
  useEffect(() => {
    handlerRef.current = handler;
  });
  useEffect(() => {
    if (!enabled) return;
    const listener = (event: KeyboardEvent) => {
      if (event.key !== key || event.repeat) return;
      if (document.querySelector("[role='dialog'][data-state='open']")) return;
      event.preventDefault();
      handlerRef.current(event);
    };
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, [key, enabled]);
}

export function useDebounced<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(id);
  }, [value, delayMs]);
  return debounced;
}

export function useDocumentTitle(title: string): void {
  useEffect(() => {
    document.title = `${title} · Tópico de Salud CSJ Lima`;
  }, [title]);
}
