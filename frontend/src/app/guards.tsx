import { ShieldAlert } from "lucide-react";
import type { ReactNode } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "@/shared/auth/AuthProvider";
import { SiteProvider } from "@/shared/auth/SiteProvider";
import { EmptyState, Spinner } from "@/shared/ui";

import { homeFor } from "./navigation";

export function FullScreenLoader() {
  return (
    <div className="grid min-h-dvh place-items-center">
      <Spinner className="size-7" label="Cargando el sistema" />
    </div>
  );
}

/** Rutas que exigen sesión. Si la contraseña es temporal, obliga a cambiarla primero. */
export function RequireAuth() {
  const { status, user } = useAuth();
  const location = useLocation();
  if (status === "loading") return <FullScreenLoader />;
  if (status === "anonymous" || !user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (user.must_change_password && location.pathname !== "/cambiar-clave") return <Navigate to="/cambiar-clave" replace />;
  return (
    <SiteProvider>
      <Outlet />
    </SiteProvider>
  );
}

/** Oculta la vista si el usuario no tiene alguno de los permisos (el backend igual los valida). */
export function RequirePermission({ any, children }: { any: string[]; children: ReactNode }) {
  const { canAny } = useAuth();
  if (!canAny(...any)) {
    return (
      <EmptyState
        icon={ShieldAlert}
        title="No tiene acceso a esta sección"
        description="Si considera que debería tenerlo, solicítelo al administrador del sistema."
      />
    );
  }
  return <>{children}</>;
}

export function HomeRedirect() {
  const { can } = useAuth();
  return <Navigate to={homeFor(can)} replace />;
}
