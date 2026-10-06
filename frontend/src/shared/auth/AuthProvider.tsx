import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { api, refreshSession, session } from "@/shared/api/client";
import type { Me, TokenResponse } from "@/shared/api/types";
import { notify } from "@/shared/lib/notify";

type Status = "loading" | "authenticated" | "anonymous";

interface AuthContextValue {
  status: Status;
  user: Me | null;
  login: (username: string, password: string) => Promise<Me>;
  logout: () => Promise<void>;
  applyToken: (token: TokenResponse) => void;
  /** Vuelve a leer el usuario (p. ej., tras crear una sede: aparece en el selector). */
  reloadUser: () => Promise<void>;
  can: (permission: string) => boolean;
  canAny: (...permissions: string[]) => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<Status>("loading");
  const [user, setUser] = useState<Me | null>(null);

  const applyToken = useCallback((token: TokenResponse) => {
    session.setToken(token.access_token);
    setUser(token.user);
    setStatus("authenticated");
  }, []);

  // Restaura la sesión al cargar (la cookie HttpOnly sobrevive a la recarga; el token no).
  useEffect(() => {
    let active = true;
    const unsubscribeRefresh = session.onRefreshed((payload) => {
      const token = payload as TokenResponse;
      if (active) {
        setUser(token.user);
        setStatus("authenticated");
      }
    });
    const unsubscribeExpired = session.onExpired(() => {
      if (!active) return;
      session.setToken(null);
      setUser(null);
      setStatus("anonymous");
      queryClient.clear();
      notify.warning("Su sesión ha finalizado", "Por seguridad, inicie sesión nuevamente.");
    });
    void refreshSession().then((ok) => {
      if (active && !ok) setStatus("anonymous");
    });
    return () => {
      active = false;
      unsubscribeRefresh();
      unsubscribeExpired();
    };
  }, [queryClient]);

  const login = useCallback(
    async (username: string, password: string) => {
      const token = await api.post<TokenResponse>("/auth/login", { username, password }, { skipRefresh: true });
      applyToken(token);
      return token.user;
    },
    [applyToken],
  );

  const logout = useCallback(async () => {
    try {
      await api.post("/auth/logout", undefined, { skipRefresh: true });
    } finally {
      session.setToken(null);
      setUser(null);
      setStatus("anonymous");
      queryClient.clear();
    }
  }, [queryClient]);

  const reloadUser = useCallback(async () => {
    setUser(await api.get<Me>("/auth/me"));
  }, []);

  const value = useMemo<AuthContextValue>(() => {
    const permissions = new Set(user?.permissions ?? []);
    return {
      status,
      user,
      login,
      logout,
      applyToken,
      reloadUser,
      can: (permission) => permissions.has(permission),
      canAny: (...list) => list.some((p) => permissions.has(p)),
    };
  }, [status, user, login, logout, applyToken, reloadUser]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth debe usarse dentro de <AuthProvider>");
  return context;
}

/** Usuario autenticado (solo en rutas protegidas). */
export function useUser(): Me {
  const { user } = useAuth();
  if (!user) throw new Error("useUser requiere una sesión activa");
  return user;
}
