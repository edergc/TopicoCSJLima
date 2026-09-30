import { FileQuestion } from "lucide-react";
import type { ComponentType, ReactNode } from "react";
import { createBrowserRouter, Link, useRouteError } from "react-router-dom";

import { Button, EmptyState } from "@/shared/ui";

import { HomeRedirect, RequireAuth, RequirePermission } from "./guards";
import { AppShell } from "./layout/AppShell";

/** Carga diferida por módulo: cada sección se descarga solo cuando se visita. */
function page(loader: () => Promise<{ default: ComponentType }>, permissions?: string[]) {
  return async () => {
    const { default: Component } = await loader();
    const element: ReactNode = <Component />;
    return {
      Component: () => (permissions ? <RequirePermission any={permissions}>{element}</RequirePermission> : element),
    };
  };
}

function RouteError() {
  const error = useRouteError();
  console.error(error);
  return (
    <EmptyState
      className="min-h-[60dvh]"
      icon={FileQuestion}
      title="No se pudo mostrar esta página"
      description="Recargue la página. Si el problema continúa, comuníquese con soporte."
      action={<Button onClick={() => window.location.reload()}>Recargar</Button>}
    />
  );
}

function NotFound() {
  return (
    <EmptyState
      className="min-h-[60dvh]"
      icon={FileQuestion}
      title="Página no encontrada"
      action={
        <Link to="/">
          <Button variant="secondary">Ir al inicio</Button>
        </Link>
      }
    />
  );
}

export const router = createBrowserRouter([
  { path: "/login", lazy: page(() => import("@/features/auth/LoginPage")) },
  { path: "/consulta", lazy: page(() => import("@/features/public/PublicStatusPage")) },
  {
    element: <RequireAuth />,
    errorElement: <RouteError />,
    children: [
      { path: "/cambiar-clave", lazy: page(() => import("@/features/auth/ChangePasswordPage")) },
      {
        element: <AppShell />,
        errorElement: <RouteError />,
        children: [
          { index: true, element: <HomeRedirect /> },
          { path: "mesa", lazy: page(() => import("@/features/desk/DeskPage"), ["queue:read"]) },
          { path: "atenciones", lazy: page(() => import("@/features/appointments/AppointmentsPage"), ["appointment:read"]) },
          { path: "trabajadores", lazy: page(() => import("@/features/workers/WorkersPage"), ["worker:read"]) },
          { path: "importaciones", lazy: page(() => import("@/features/imports/ImportsPage"), ["import:manage"]) },
          { path: "reportes", lazy: page(() => import("@/features/reports/ReportsPage"), ["report:read"]) },
          { path: "auditoria", lazy: page(() => import("@/features/audit/AuditPage"), ["audit:read"]) },
          { path: "admin/usuarios", lazy: page(() => import("@/features/admin/UsersPage"), ["user:read", "role:read"]) },
          { path: "admin/sedes", lazy: page(() => import("@/features/admin/SitesPage"), ["site:configure"]) },
          {
            path: "admin/configuracion",
            lazy: page(() => import("@/features/admin/ConfigurationPage"), ["catalog:manage", "template:manage", "parameter:manage"]),
          },
          {
            path: "sin-acceso",
            element: <EmptyState icon={FileQuestion} title="Su usuario no tiene secciones habilitadas" description="Solicite permisos al administrador." />,
          },
          { path: "*", element: <NotFound /> },
        ],
      },
    ],
  },
]);
