import {
  Building2,
  FileSpreadsheet,
  LayoutGrid,
  ListChecks,
  type LucideIcon,
  BarChart3,
  Settings2,
  ShieldCheck,
  UserCog,
  Users,
} from "lucide-react";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  /** Basta con tener uno de estos permisos. */
  permissions: string[];
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const NAVIGATION: NavGroup[] = [
  {
    label: "Operación",
    items: [
      { to: "/mesa", label: "Mesa de atención", icon: LayoutGrid, permissions: ["queue:read"] },
      { to: "/atenciones", label: "Atenciones", icon: ListChecks, permissions: ["appointment:read"] },
    ],
  },
  {
    label: "Gestión",
    items: [
      { to: "/trabajadores", label: "Trabajadores", icon: Users, permissions: ["worker:read"] },
      { to: "/importaciones", label: "Importaciones", icon: FileSpreadsheet, permissions: ["import:manage"] },
      { to: "/reportes", label: "Reportes", icon: BarChart3, permissions: ["report:read"] },
    ],
  },
  {
    label: "Control",
    items: [{ to: "/auditoria", label: "Auditoría", icon: ShieldCheck, permissions: ["audit:read"] }],
  },
  {
    label: "Administración",
    items: [
      { to: "/admin/usuarios", label: "Usuarios y roles", icon: UserCog, permissions: ["user:read", "role:read"] },
      { to: "/admin/sedes", label: "Sedes y horarios", icon: Building2, permissions: ["site:configure"] },
      {
        to: "/admin/configuracion",
        label: "Catálogos y parámetros",
        icon: Settings2,
        permissions: ["catalog:manage", "template:manage", "parameter:manage"],
      },
    ],
  },
];

/** Primera ruta a la que el usuario tiene acceso (destino tras iniciar sesión). */
export function homeFor(can: (permission: string) => boolean): string {
  for (const group of NAVIGATION) {
    for (const item of group.items) {
      if (item.permissions.some(can)) return item.to;
    }
  }
  return "/sin-acceso";
}
