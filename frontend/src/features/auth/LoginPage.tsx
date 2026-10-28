import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowUpFromLine, ChevronRight, KeyRound, LogIn, Search, UserRound } from "lucide-react";
import { cloneElement, useState, type ReactElement } from "react";
import { useForm } from "react-hook-form";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { z } from "zod";

import { FullScreenLoader } from "@/app/guards";
import { homeFor } from "@/app/navigation";
import { useAuth } from "@/shared/auth/AuthProvider";
import { useDocumentTitle } from "@/shared/lib/hooks";
import { errorMessage } from "@/shared/lib/notify";
import { Button, Callout, Field, Input, PasswordInput } from "@/shared/ui";

import { AuthLayout } from "./AuthLayout";
import { capsLockOn } from "./password";

const schema = z.object({
  username: z.string().trim().min(1, "Ingrese su usuario."),
  password: z.string().min(1, "Ingrese su contraseña."),
});
type FormValues = z.infer<typeof schema>;

// «Recordar mi usuario»: solo el nombre de usuario, en este equipo (nunca la contraseña).
const REMEMBER_KEY = "topico.lastUser";

function readRemembered(): string {
  try {
    return localStorage.getItem(REMEMBER_KEY) ?? "";
  } catch {
    return "";
  }
}

function saveRemembered(username: string | null): void {
  try {
    if (username) localStorage.setItem(REMEMBER_KEY, username);
    else localStorage.removeItem(REMEMBER_KEY);
  } catch {
    /* sin almacenamiento disponible */
  }
}

/**
 * Campo con ícono a la izquierda (decorativo). <Field> inyecta id y atributos ARIA en su hijo directo:
 * aquí se reenvían al control real para que la etiqueta y los mensajes de error queden asociados.
 */
function WithIcon({
  icon: Icon,
  children,
  ...fieldProps
}: { icon: typeof UserRound; children: ReactElement<Record<string, unknown>> } & Record<string, unknown>) {
  return (
    <div className="relative">
      <Icon className="pointer-events-none absolute top-1/2 left-3.5 z-10 size-4 -translate-y-1/2 text-ink-soft" aria-hidden />
      {cloneElement(children, fieldProps)}
    </div>
  );
}

/** Estado de navegación con el que otras pantallas dejan un aviso en el ingreso. */
export interface LoginNotice {
  notice?: string;
  username?: string;
  from?: string;
}

export default function LoginPage() {
  useDocumentTitle("Iniciar sesión");
  const { status, user, login, can } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const state = (location.state as LoginNotice | null) ?? {};
  const [serverError, setServerError] = useState<string | null>(null);
  const [capsLock, setCapsLock] = useState(false);
  const [remembered] = useState(readRemembered);
  const [remember, setRemember] = useState(Boolean(remembered));
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { username: state.username ?? remembered, password: "" },
  });

  if (status === "loading") return <FullScreenLoader />;
  if (status === "authenticated" && user) return <Navigate to="/" replace />;

  const onSubmit = handleSubmit(async ({ username, password }) => {
    setServerError(null);
    try {
      const me = await login(username, password);
      saveRemembered(remember ? username.trim() : null);
      const permissions = new Set(me.permissions);
      navigate(me.must_change_password ? "/cambiar-clave" : (state.from ?? homeFor((p) => permissions.has(p) || can(p))), {
        replace: true,
      });
    } catch (error) {
      setServerError(errorMessage(error));
    }
  });

  return (
    <AuthLayout title="Iniciar sesión" subtitle="Ingrese con su usuario (DNI) y la contraseña asignada por la administración.">
      <form onSubmit={onSubmit} noValidate className="space-y-5">
        {state.notice && !serverError && <Callout tone="success">{state.notice}</Callout>}
        {serverError && <Callout tone="danger">{serverError}</Callout>}
        <Field label="Usuario" error={errors.username?.message}>
          <WithIcon icon={UserRound}>
          <Input
            autoComplete="username"
            autoFocus={!state.username && !remembered}
            autoCapitalize="none"
            spellCheck={false}
            className="h-12 pl-10 text-[0.9375rem]"
            placeholder="Su usuario o DNI"
            {...register("username")}
          />
          </WithIcon>
        </Field>
        <Field
          label="Contraseña"
          error={errors.password?.message}
          hint={
            capsLock ? (
              <span className="flex items-center gap-1 text-warning">
                <ArrowUpFromLine className="size-3.5" aria-hidden /> Bloq Mayús está activado.
              </span>
            ) : undefined
          }
          labelAction={
            <Link to="/recuperar-clave" className="text-[0.8125rem] font-medium text-brand-700 hover:underline">
              ¿Olvidó su contraseña?
            </Link>
          }
        >
          <WithIcon icon={KeyRound}>
          <PasswordInput
            autoComplete="current-password"
            autoFocus={Boolean(state.username || remembered)}
            className="h-12 pl-10 text-[0.9375rem]"
            onKeyUp={(e) => setCapsLock(capsLockOn(e))}
            onKeyDown={(e) => setCapsLock(capsLockOn(e))}
            {...register("password")}
          />
          </WithIcon>
        </Field>
        <label className="flex w-fit cursor-pointer items-center gap-2.5 text-sm text-ink-muted select-none">
          <input
            type="checkbox"
            checked={remember}
            onChange={(e) => setRemember(e.target.checked)}
            className="size-4 rounded border-line-strong accent-brand-700"
          />
          Recordar mi usuario en este equipo
        </label>
        <Button type="submit" size="lg" className="h-12 w-full text-[0.9375rem]" loading={isSubmitting} icon={<LogIn className="size-4" />}>
          Ingresar
        </Button>
      </form>

      <div className="mt-7 border-t border-line pt-5">
        <Link
          to="/consulta"
          className="group flex items-center gap-3 rounded-xl p-2 -m-2 transition hover:bg-sunken/70"
        >
          <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-brand-50 text-brand-700">
            <Search className="size-[18px]" aria-hidden />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block text-sm font-medium text-ink">¿Es trabajador? Consulte su turno</span>
            <span className="block text-[0.8125rem] text-ink-soft">Sin usuario: con su DNI y su código de turno.</span>
          </span>
          <ChevronRight className="size-4 text-ink-faint transition group-hover:translate-x-0.5 group-hover:text-brand-700" aria-hidden />
        </Link>
      </div>
    </AuthLayout>
  );
}
