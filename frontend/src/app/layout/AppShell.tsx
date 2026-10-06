import * as DialogPrimitive from "@radix-ui/react-dialog";
import { ChevronDown, KeyRound, LogOut, Menu as MenuIcon, X } from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { NAVIGATION } from "@/app/navigation";
import { api } from "@/shared/api/client";
import { useAuth, useUser } from "@/shared/auth/AuthProvider";
import { useSite } from "@/shared/auth/SiteProvider";
import { cn } from "@/shared/lib/cn";
import { fmt, todayIso } from "@/shared/lib/format";
import { useNow } from "@/shared/lib/hooks";
import { syncServerTime } from "@/shared/lib/serverTime";
import { IconButton, Menu, MenuContent, MenuItem, MenuLabel, MenuSeparator, MenuTrigger, Segmented, Select } from "@/shared/ui";

import { AccessibilityMenu } from "@/shared/a11y/AccessibilityMenu";
import { useBranding } from "@/shared/branding/branding";

import { BrandMark } from "./BrandMark";

const ROLE_LABEL: Record<string, string> = {
  ADMIN: "Administrador(a)",
  SUPERVISOR: "Supervisor(a)",
  OPERATOR: "Encargado(a) del tópico",
  AUDITOR: "Auditor(a)",
};

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { can } = useAuth();
  const branding = useBranding();
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 px-5 pt-5 pb-6">
        <BrandMark />
        <div className="min-w-0 leading-tight">
          <p className="text-[0.9375rem] font-semibold tracking-tight text-white">Tópico de Salud</p>
          <p className="text-xs text-white/60">{branding.institution_name}</p>
        </div>
      </div>
      <nav className="flex-1 space-y-6 overflow-y-auto px-3 pb-6" aria-label="Navegación principal">
        {NAVIGATION.map((group) => {
          const items = group.items.filter((item) => item.permissions.some(can));
          if (items.length === 0) return null;
          return (
            <div key={group.label}>
              <p className="px-3 pb-2 text-[0.6875rem] font-semibold tracking-[0.1em] text-white/40 uppercase">{group.label}</p>
              <ul className="space-y-0.5">
                {items.map((item) => (
                  <li key={item.to}>
                    <NavLink
                      to={item.to}
                      onClick={onNavigate}
                      className={({ isActive }) =>
                        cn(
                          "group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                          isActive ? "bg-white/12 text-white shadow-[inset_2px_0_0_0_#fff]" : "text-white/70 hover:bg-white/6 hover:text-white",
                        )
                      }
                    >
                      <item.icon className="size-[18px] shrink-0 opacity-90" aria-hidden />
                      {item.label}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </nav>
      <p className="px-5 pb-4 text-[0.6875rem] text-white/35">{branding.org_name} · v0.1</p>
    </div>
  );
}

function SiteSwitcher() {
  const { sites, site, setSiteId } = useSite();
  if (!site) return <span className="text-sm text-danger">Sin sede asignada</span>;
  if (sites.length === 1) {
    return (
      <span className="inline-flex h-8 items-center rounded-lg bg-sunken px-3 text-[0.8125rem] font-medium text-ink">
        {site.name}
      </span>
    );
  }
  if (sites.length <= 3) {
    return (
      <Segmented
        label="Sede de trabajo"
        value={String(site.id)}
        onChange={(v) => setSiteId(Number(v))}
        options={sites.map((s) => ({ value: String(s.id), label: s.short_name }))}
      />
    );
  }
  return (
    <Select aria-label="Sede de trabajo" value={site.id} onChange={(e) => setSiteId(Number(e.target.value))} className="h-8 w-56">
      {sites.map((s) => (
        <option key={s.id} value={s.id}>
          {s.name}
        </option>
      ))}
    </Select>
  );
}

function Clock() {
  const now = useNow(15_000);
  useEffect(() => {
    const sentAt = Date.now();
    void api
      .get<{ server_time: string }>("/health")
      .then((h) => syncServerTime(h.server_time, (sentAt + Date.now()) / 2))
      .catch(() => undefined);
  }, []);
  return (
    <div className="hidden text-right leading-tight sm:block">
      <p className="tabular text-sm font-semibold text-ink">{fmt.time(now)}</p>
      <p className="text-xs text-ink-soft">{fmt.longDate(todayIso(new Date(now)))}</p>
    </div>
  );
}

function UserMenu() {
  const user = useUser();
  const { logout } = useAuth();
  const navigate = useNavigate();
  const initials = user.full_name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0])
    .join("")
    .toUpperCase();
  return (
    <Menu>
      <MenuTrigger className="flex items-center gap-2.5 rounded-xl py-1 pr-2 pl-1 hover:bg-sunken" aria-label="Menú de usuario">
        <span className="grid size-8 place-items-center rounded-lg bg-brand-700 text-xs font-semibold text-white">{initials}</span>
        <span className="hidden text-left leading-tight md:block">
          <span className="block max-w-40 truncate text-[0.8125rem] font-semibold text-ink">{user.full_name}</span>
          <span className="block text-xs text-ink-soft">{ROLE_LABEL[user.roles[0] ?? ""] ?? user.roles[0]}</span>
        </span>
        <ChevronDown className="size-4 text-ink-soft" aria-hidden />
      </MenuTrigger>
      <MenuContent>
        <MenuLabel>{user.username}</MenuLabel>
        <MenuItem onSelect={() => navigate("/cambiar-clave")}>
          <KeyRound className="size-4" /> Cambiar contraseña
        </MenuItem>
        <MenuSeparator />
        <MenuItem danger onSelect={() => void logout().then(() => navigate("/login", { replace: true }))}>
          <LogOut className="size-4" /> Cerrar sesión
        </MenuItem>
      </MenuContent>
    </Menu>
  );
}

export function AppShell() {
  const [mobileOpen, setMobileOpen] = useState(false);
  return (
    <div className="flex min-h-dvh">
      <a href="#contenido" className="sr-only z-50 rounded bg-panel px-3 py-2 focus:not-sr-only focus:fixed focus:top-2 focus:left-2">
        Saltar al contenido
      </a>
      <aside className="sticky top-0 hidden h-dvh w-64 shrink-0 bg-brand-900 bg-[radial-gradient(120%_60%_at_0%_0%,var(--color-brand-700)_0%,transparent_60%)] lg:block">
        <Sidebar />
      </aside>

      <DialogPrimitive.Root open={mobileOpen} onOpenChange={setMobileOpen}>
        <DialogPrimitive.Portal>
          <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-ink/40 lg:hidden" />
          <DialogPrimitive.Content className="fixed inset-y-0 left-0 z-50 w-72 bg-brand-900 lg:hidden" aria-describedby={undefined}>
            <DialogPrimitive.Title className="sr-only">Navegación</DialogPrimitive.Title>
            <DialogPrimitive.Close className="absolute top-4 right-3 grid size-8 place-items-center rounded-lg text-white/70 hover:bg-white/10" aria-label="Cerrar menú">
              <X className="size-4" />
            </DialogPrimitive.Close>
            <Sidebar onNavigate={() => setMobileOpen(false)} />
          </DialogPrimitive.Content>
        </DialogPrimitive.Portal>
      </DialogPrimitive.Root>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-line bg-panel/90 px-4 backdrop-blur md:px-6">
          <IconButton label="Abrir menú" className="lg:hidden" onClick={() => setMobileOpen(true)} icon={<MenuIcon className="size-5" />} />
          <SiteSwitcher />
          <div className="ml-auto flex items-center gap-4">
            <Clock />
            <div className="hidden h-8 w-px bg-line sm:block" />
            <AccessibilityMenu />
            <UserMenu />
          </div>
        </header>
        <main id="contenido" className="mx-auto w-full max-w-[1600px] flex-1 px-4 py-6 md:px-6 lg:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
