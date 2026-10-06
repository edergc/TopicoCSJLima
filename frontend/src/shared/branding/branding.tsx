import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";

import { api } from "@/shared/api/client";
import type { Branding } from "@/shared/api/types";

export const DEFAULT_BRAND_COLOR = "#7a1e2c";

const FALLBACK: Branding = {
  org_name: "Poder Judicial del Perú",
  institution_name: "Corte Superior de Justicia de Lima",
  system_name: "Sistema de Gestión del Tópico de Salud",
  primary_color: DEFAULT_BRAND_COLOR,
  logo_updated_at: null,
};

/** Identidad visual configurada (pública: también la usan el login, la consulta y la pantalla de sala). */
export function useBranding(): Branding {
  const { data } = useQuery({
    queryKey: ["branding"],
    queryFn: () => api.get<Branding>("/public/branding", undefined),
    staleTime: 5 * 60_000,
    retry: 1,
  });
  return data ?? FALLBACK;
}

export function logoUrl(branding: Branding): string | null {
  return branding.logo_updated_at ? `/api/v1/public/branding/logo?v=${encodeURIComponent(branding.logo_updated_at)}` : null;
}

/** Escala de la marca a partir del color institucional (mezclas en oklab, mismo papel que la paleta original). */
export function brandScale(color: string): Record<string, string> {
  const mix = (pct: number, other: "white" | "black") => `color-mix(in oklab, ${color} ${pct}%, ${other})`;
  return {
    "--color-brand-50": mix(5, "white"),
    "--color-brand-100": mix(12, "white"),
    "--color-brand-200": mix(28, "white"),
    "--color-brand-300": mix(48, "white"),
    "--color-brand-500": mix(78, "white"),
    "--color-brand-600": mix(90, "white"),
    "--color-brand-700": color,
    "--color-brand-800": mix(80, "black"),
    "--color-brand-900": mix(58, "black"),
  };
}

/** Aplica el color institucional configurado a toda la interfaz (si difiere del predeterminado). */
export function BrandingEffect() {
  const { primary_color } = useBranding();
  useEffect(() => {
    const root = document.documentElement;
    const vars = brandScale(primary_color);
    if (primary_color.toLowerCase() === DEFAULT_BRAND_COLOR) {
      Object.keys(vars).forEach((k) => root.style.removeProperty(k));
      return;
    }
    Object.entries(vars).forEach(([k, v]) => root.style.setProperty(k, v));
  }, [primary_color]);
  return null;
}
