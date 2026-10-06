import { useSyncExternalStore } from "react";

/**
 * Preferencias de accesibilidad de este equipo/navegador (no del usuario): tamaño de letra y alto contraste.
 * Se guardan localmente y se aplican antes de dibujar la interfaz (sin parpadeo).
 */
export interface A11yPrefs {
  scale: number;
  contrast: boolean;
}

export const SCALES = [1, 1.125, 1.25, 1.5] as const;
const KEY = "topico.a11y";
const DEFAULT: A11yPrefs = { scale: 1, contrast: false };

let current = read();
const listeners = new Set<() => void>();

function read(): A11yPrefs {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) ?? "null") as Partial<A11yPrefs> | null;
    const scale = SCALES.includes(raw?.scale as (typeof SCALES)[number]) ? (raw!.scale as number) : 1;
    return { scale, contrast: raw?.contrast === true };
  } catch {
    return DEFAULT;
  }
}

/**
 * Aplica las preferencias al documento: tamaño del texto (rem; el espaciado está en px, así el diseño
 * se reacomoda sin encogerse — WCAG 1.4.4) y paleta de alto contraste.
 */
export function applyA11y(prefs: A11yPrefs = current): void {
  const root = document.documentElement;
  if (prefs.contrast) root.dataset.contrast = "high";
  else delete root.dataset.contrast;
  root.style.fontSize = prefs.scale === 1 ? "" : `${prefs.scale * 100}%`;
}

export function setA11y(patch: Partial<A11yPrefs>): void {
  current = { ...current, ...patch };
  try {
    localStorage.setItem(KEY, JSON.stringify(current));
  } catch {
    /* sin almacenamiento: se mantiene durante la sesión */
  }
  applyA11y(current);
  listeners.forEach((l) => l());
}

export function useA11y(): A11yPrefs {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => current,
  );
}
