import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

import type { SiteRef } from "@/shared/api/types";

import { useUser } from "./AuthProvider";

const STORAGE_KEY = "topico.site";

interface SiteContextValue {
  sites: SiteRef[];
  site: SiteRef | null;
  setSiteId: (id: number) => void;
}

const SiteContext = createContext<SiteContextValue | null>(null);

function readStored(): number | null {
  try {
    const value = Number(localStorage.getItem(STORAGE_KEY));
    return Number.isFinite(value) && value > 0 ? value : null;
  } catch {
    return null;
  }
}

/** Sede de trabajo actual: solo entre las sedes autorizadas del usuario (el backend igual lo valida). */
export function SiteProvider({ children }: { children: ReactNode }) {
  const user = useUser();
  const sites = user.sites;
  const [siteId, setSiteIdState] = useState<number | null>(() => readStored());

  const site = useMemo(() => sites.find((s) => s.id === siteId) ?? sites[0] ?? null, [sites, siteId]);

  const value = useMemo<SiteContextValue>(
    () => ({
      sites,
      site,
      setSiteId: (id: number) => {
        setSiteIdState(id);
        try {
          localStorage.setItem(STORAGE_KEY, String(id));
        } catch {
          /* almacenamiento no disponible: se mantiene solo en memoria */
        }
      },
    }),
    [sites, site],
  );

  return <SiteContext.Provider value={value}>{children}</SiteContext.Provider>;
}

export function useSite(): SiteContextValue {
  const context = useContext(SiteContext);
  if (!context) throw new Error("useSite debe usarse dentro de <SiteProvider>");
  return context;
}
