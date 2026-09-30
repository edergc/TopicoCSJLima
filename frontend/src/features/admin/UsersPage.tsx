import { Check, Copy, KeyRound, Lock, LockOpen, Plus, ShieldCheck, UserCog, UserX } from "lucide-react";
import { Fragment, useMemo, useState } from "react";

import type { Permission, Role, User, UserWithPassword } from "@/shared/api/types";
import { useAuth, useUser } from "@/shared/auth/AuthProvider";
import { cn } from "@/shared/lib/cn";
import { fmt } from "@/shared/lib/format";
import { useDebounced, useDocumentTitle } from "@/shared/lib/hooks";
import { errorMessage, notify } from "@/shared/lib/notify";
import {
  Badge,
  Button,
  Callout,
  Card,
  ConfirmDialog,
  DataTable,
  Field,
  Input,
  Modal,
  PageHeader,
  Pagination,
  SearchInput,
  Skeleton,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  type Column,
} from "@/shared/ui";

import {
  useAllSites,
  useCreateUser,
  usePermissions,
  useResetPassword,
  useRoles,
  useSetRolePermissions,
  useUnlockUser,
  useUpdateUser,
  useUsers,
} from "./api";

const MODULE_LABEL: Record<string, string> = {
  users: "Usuarios",
  workers: "Trabajadores",
  imports: "Importaciones",
  sites: "Sedes",
  agenda: "Agenda",
  queue: "Cola",
  appointments: "Atenciones",
  notifications: "Notificaciones",
  reports: "Reportes",
  audit: "Auditoría",
  admin: "Administración",
};

function TemporaryPassword({ result, onClose }: { result: UserWithPassword; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  const copy = () =>
    void navigator.clipboard.writeText(result.temporary_password).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  return (
    <Modal
      open
      onOpenChange={(o) => !o && onClose()}
      size="sm"
      dismissable={false}
      title="Contraseña temporal"
      description={`Entréguela de forma segura a ${result.full_name}. No volverá a mostrarse.`}
      footer={<Button onClick={onClose}>Entendido</Button>}
    >
      <div className="space-y-4">
        <div className="flex items-center gap-2 rounded-xl border border-line bg-surface p-3">
          <code className="tabular flex-1 font-mono text-lg font-semibold tracking-wider select-all">{result.temporary_password}</code>
          <Button variant="secondary" size="sm" onClick={copy} icon={copied ? <Check className="size-4" /> : <Copy className="size-4" />}>
            {copied ? "Copiada" : "Copiar"}
          </Button>
        </div>
        <p className="text-[13px] text-ink-muted">
          Usuario: <span className="font-semibold text-ink">{result.username}</span>. Al ingresar por primera vez se le pedirá
          definir una contraseña personal.
        </p>
      </div>
    </Modal>
  );
}

function CheckboxGroup<T extends string | number>({
  legend,
  options,
  value,
  onChange,
}: {
  legend: string;
  options: { value: T; label: string; description?: string }[];
  value: T[];
  onChange: (value: T[]) => void;
}) {
  return (
    <fieldset>
      <legend className="mb-2 text-[13px] font-medium">{legend}</legend>
      <div className="grid gap-2 sm:grid-cols-2">
        {options.map((option) => {
          const checked = value.includes(option.value);
          return (
            <label
              key={option.value}
              className={cn(
                "flex cursor-pointer items-start gap-3 rounded-lg border px-3 py-2.5 text-sm",
                checked ? "border-brand-600 bg-brand-50/60" : "border-line hover:bg-surface",
              )}
            >
              <input
                type="checkbox"
                className="mt-0.5 size-4 accent-brand-700"
                checked={checked}
                onChange={() => onChange(checked ? value.filter((v) => v !== option.value) : [...value, option.value])}
              />
              <span>
                <span className="font-medium">{option.label}</span>
                {option.description && <span className="block text-xs text-ink-soft">{option.description}</span>}
              </span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}

function UserFormModal({ user, onClose, onCreated }: { user?: User; onClose: () => void; onCreated: (r: UserWithPassword) => void }) {
  const roles = useRoles();
  const sites = useAllSites();
  const create = useCreateUser();
  const update = useUpdateUser();
  const [username, setUsername] = useState(user?.username ?? "");
  const [fullName, setFullName] = useState(user?.full_name ?? "");
  const [email, setEmail] = useState(user?.email ?? "");
  const [roleCodes, setRoleCodes] = useState<string[]>(user?.roles ?? ["OPERATOR"]);
  const [siteIds, setSiteIds] = useState<number[]>(user?.sites.map((s) => s.id) ?? []);
  const mutation = user ? update : create;
  const valid = /^[a-z0-9][a-z0-9._-]{2,49}$/.test(username.trim().toLowerCase()) && fullName.trim().length >= 3 && roleCodes.length > 0;

  const submit = () => {
    const body = { full_name: fullName.trim(), email: email.trim() || null, role_codes: roleCodes, site_ids: siteIds };
    if (user) {
      update.mutate({ id: user.public_id, body }, { onSuccess: () => (notify.success("Usuario actualizado"), onClose()) });
    } else {
      create.mutate({ ...body, username: username.trim().toLowerCase() }, { onSuccess: (r) => (onClose(), onCreated(r)) });
    }
  };

  return (
    <Modal
      open
      onOpenChange={(o) => !o && onClose()}
      size="lg"
      dismissable={false}
      title={user ? `Editar ${user.username}` : "Nuevo usuario"}
      description="Los permisos se otorgan mediante roles. Las sedes limitan dónde puede operar."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button onClick={submit} loading={mutation.isPending} disabled={!valid}>
            {user ? "Guardar cambios" : "Crear usuario"}
          </Button>
        </>
      }
    >
      <div className="space-y-5">
        {mutation.isError && <Callout tone="danger">{errorMessage(mutation.error)}</Callout>}
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Usuario" required hint="Minúsculas, sin espacios (p. ej., nombre.apellido).">
            <Input value={username} onChange={(e) => setUsername(e.target.value)} disabled={Boolean(user)} autoCapitalize="none" />
          </Field>
          <Field label="Nombre completo" required>
            <Input value={fullName} onChange={(e) => setFullName(e.target.value)} />
          </Field>
          <Field label="Correo institucional" className="sm:col-span-2">
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </Field>
        </div>
        {roles.data ? (
          <CheckboxGroup
            legend="Roles"
            value={roleCodes}
            onChange={setRoleCodes}
            options={roles.data.map((r) => ({ value: r.code, label: r.name, description: r.description ?? undefined }))}
          />
        ) : (
          <Skeleton className="h-24" />
        )}
        {sites.data && (
          <CheckboxGroup legend="Sedes autorizadas" value={siteIds} onChange={setSiteIds} options={sites.data.map((s) => ({ value: s.id, label: s.name }))} />
        )}
      </div>
    </Modal>
  );
}

function UsersTab() {
  const me = useUser();
  const { can } = useAuth();
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<User | "new" | null>(null);
  const [created, setCreated] = useState<UserWithPassword | null>(null);
  const [confirm, setConfirm] = useState<{ user: User; kind: "reset" | "deactivate" } | null>(null);
  const query = useDebounced(q.trim(), 350);
  const { data, isLoading } = useUsers({ q: query || undefined, page, size: 25 });
  const reset = useResetPassword();
  const update = useUpdateUser();
  const unlock = useUnlockUser();
  const canManage = can("user:manage");

  const columns: Column<User>[] = [
    {
      key: "user",
      header: "Usuario",
      cell: (u) => (
        <div>
          <p className="font-medium">{u.full_name}</p>
          <p className="text-xs text-ink-soft">{u.username}</p>
        </div>
      ),
    },
    { key: "roles", header: "Roles", cell: (u) => <div className="flex flex-wrap gap-1">{u.roles.map((r) => <Badge key={r} tone="brand">{r}</Badge>)}</div> },
    { key: "sites", header: "Sedes", cell: (u) => u.sites.map((s) => s.short_name).join(", ") || "—", hideOnMobile: true },
    { key: "last", header: "Último ingreso", cell: (u) => <span className="tabular">{u.last_login_at ? fmt.dateTime(u.last_login_at) : "Nunca"}</span>, hideOnMobile: true },
    {
      key: "status",
      header: "Estado",
      cell: (u) =>
        !u.is_active ? (
          <Badge>Inactivo</Badge>
        ) : u.is_locked ? (
          <Badge tone="danger">
            <Lock className="size-3" /> Bloqueado
          </Badge>
        ) : u.must_change_password ? (
          <Badge tone="warning">Clave temporal</Badge>
        ) : (
          <Badge tone="success">Activo</Badge>
        ),
    },
    {
      key: "actions",
      header: <span className="sr-only">Acciones</span>,
      className: "text-right",
      cell: (u) =>
        canManage && (
          <div className="flex justify-end gap-1" onClick={(e) => e.stopPropagation()}>
            {u.is_locked && (
              <Button size="sm" variant="ghost" icon={<LockOpen className="size-4" />} onClick={() => unlock.mutate(u.public_id, { onSuccess: () => notify.success("Usuario desbloqueado") })}>
                Desbloquear
              </Button>
            )}
            <Button size="sm" variant="ghost" icon={<KeyRound className="size-4" />} onClick={() => setConfirm({ user: u, kind: "reset" })}>
              Restablecer
            </Button>
            {u.is_active && u.public_id !== me.public_id && (
              <Button size="sm" variant="ghost" className="text-danger" icon={<UserX className="size-4" />} onClick={() => setConfirm({ user: u, kind: "deactivate" })}>
                Desactivar
              </Button>
            )}
            {!u.is_active && (
              <Button size="sm" variant="ghost" onClick={() => update.mutate({ id: u.public_id, body: { is_active: true } }, { onSuccess: () => notify.success("Usuario reactivado") })}>
                Reactivar
              </Button>
            )}
          </div>
        ),
    },
  ];

  return (
    <Card>
      <div className="flex flex-wrap items-center gap-3 border-b border-line p-4">
        <SearchInput value={q} onChange={(v) => (setQ(v), setPage(1))} label="Buscar por usuario o nombre" className="w-full max-w-sm" />
        {canManage && (
          <Button className="ml-auto" onClick={() => setEditing("new")} icon={<Plus className="size-4" />}>
            Nuevo usuario
          </Button>
        )}
      </div>
      <DataTable
        columns={columns}
        rows={data?.items}
        rowKey={(u) => u.public_id}
        loading={isLoading}
        onRowClick={canManage ? (u) => setEditing(u) : undefined}
        caption="Usuarios"
      />
      {data && data.total > 25 && <Pagination page={page} size={25} total={data.total} onPageChange={setPage} />}

      {editing && <UserFormModal user={editing === "new" ? undefined : editing} onClose={() => setEditing(null)} onCreated={setCreated} />}
      {created && <TemporaryPassword result={created} onClose={() => setCreated(null)} />}
      <ConfirmDialog
        open={confirm !== null}
        onOpenChange={(o) => !o && setConfirm(null)}
        tone="danger"
        title={confirm?.kind === "reset" ? "Restablecer contraseña" : "Desactivar usuario"}
        description={
          confirm?.kind === "reset"
            ? "Se generará una contraseña temporal y se cerrarán sus sesiones abiertas."
            : "No podrá ingresar al sistema. Su historial y auditoría se conservan."
        }
        confirmLabel={confirm?.kind === "reset" ? "Restablecer" : "Desactivar"}
        loading={reset.isPending || update.isPending}
        onConfirm={() => {
          if (!confirm) return;
          if (confirm.kind === "reset") {
            reset.mutate(confirm.user.public_id, { onSuccess: (r) => (setConfirm(null), setCreated(r)), onError: (e) => notify.error(e) });
          } else {
            update.mutate(
              { id: confirm.user.public_id, body: { is_active: false } },
              { onSuccess: () => (setConfirm(null), notify.success("Usuario desactivado")), onError: (e) => notify.error(e) },
            );
          }
        }}
      />
    </Card>
  );
}

function RolesTab() {
  const { can } = useAuth();
  const roles = useRoles();
  const permissions = usePermissions();
  const save = useSetRolePermissions();
  const [draft, setDraft] = useState<Record<number, Set<string>>>({});
  const canManage = can("role:manage");

  const grouped = useMemo(() => {
    const map = new Map<string, Permission[]>();
    for (const p of permissions.data ?? []) map.set(p.module, [...(map.get(p.module) ?? []), p]);
    return [...map.entries()];
  }, [permissions.data]);

  if (!roles.data || !permissions.data) return <Skeleton className="h-96" />;

  const current = (role: Role) => draft[role.id] ?? new Set(role.permissions.map((p) => p.code));
  const toggle = (role: Role, code: string) => {
    const next = new Set(current(role));
    if (next.has(code)) next.delete(code);
    else next.add(code);
    setDraft((d) => ({ ...d, [role.id]: next }));
  };
  const dirty = Object.keys(draft).length > 0;

  return (
    <Card>
      <div className="flex flex-wrap items-center gap-3 border-b border-line p-4">
        <p className="text-sm text-ink-muted">
          <ShieldCheck className="mr-1 inline size-4 text-brand-700" />
          Cada cambio de permisos queda auditado. El rol Administrador conserva siempre la gestión de usuarios y roles.
        </p>
        {canManage && dirty && (
          <div className="ml-auto flex gap-2">
            <Button variant="secondary" onClick={() => setDraft({})}>
              Descartar
            </Button>
            <Button
              loading={save.isPending}
              onClick={async () => {
                try {
                  for (const [roleId, codes] of Object.entries(draft)) {
                    await save.mutateAsync({ roleId: Number(roleId), codes: [...codes] });
                  }
                  setDraft({});
                  notify.success("Permisos actualizados");
                } catch (e) {
                  notify.error(e);
                }
              }}
            >
              Guardar cambios
            </Button>
          </div>
        )}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] text-sm">
          <thead>
            <tr className="border-b border-line bg-surface">
              <th scope="col" className="px-4 py-3 text-left text-xs font-semibold tracking-wide text-ink-soft uppercase">
                Permiso
              </th>
              {roles.data.map((role) => (
                <th key={role.id} scope="col" className="px-3 py-3 text-center text-xs font-semibold text-ink">
                  {role.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {grouped.map(([module, perms]) => (
              <Fragment key={module}>
                <tr>
                  <th colSpan={roles.data.length + 1} scope="colgroup" className="bg-sunken/60 px-4 py-2 text-left text-xs font-semibold tracking-wide text-ink-muted uppercase">
                    {MODULE_LABEL[module] ?? module}
                  </th>
                </tr>
                {perms.map((p) => (
                  <tr key={p.code} className="border-b border-line">
                    <td className="px-4 py-2.5">
                      <p className="text-ink">{p.description}</p>
                      <p className="font-mono text-[11px] text-ink-faint">{p.code}</p>
                    </td>
                    {roles.data.map((role) => (
                      <td key={role.id} className="px-3 py-2.5 text-center">
                        <input
                          type="checkbox"
                          aria-label={`${role.name}: ${p.description}`}
                          className="size-4 accent-brand-700 disabled:opacity-60"
                          checked={current(role).has(p.code)}
                          disabled={!canManage}
                          onChange={() => toggle(role, p.code)}
                        />
                      </td>
                    ))}
                  </tr>
                ))}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

export default function UsersPage() {
  useDocumentTitle("Usuarios y roles");
  const { can } = useAuth();
  return (
    <div>
      <PageHeader eyebrow="Administración" title="Usuarios y roles" description="Cuentas del personal, roles, sedes autorizadas y permisos." />
      <Tabs defaultValue={can("user:read") ? "users" : "roles"}>
        <TabsList>
          {can("user:read") && (
            <TabsTrigger value="users">
              <UserCog className="size-4" /> Usuarios
            </TabsTrigger>
          )}
          {can("role:read") && (
            <TabsTrigger value="roles">
              <ShieldCheck className="size-4" /> Roles y permisos
            </TabsTrigger>
          )}
        </TabsList>
        <TabsContent value="users">
          <UsersTab />
        </TabsContent>
        <TabsContent value="roles">
          <RolesTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
