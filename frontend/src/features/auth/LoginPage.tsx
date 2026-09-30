import { zodResolver } from "@hookform/resolvers/zod";
import { LockKeyhole, LogIn, ShieldCheck, Timer, Users } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { z } from "zod";

import { FullScreenLoader } from "@/app/guards";
import { BrandMark } from "@/app/layout/BrandMark";
import { homeFor } from "@/app/navigation";
import { useAuth } from "@/shared/auth/AuthProvider";
import { errorMessage } from "@/shared/lib/notify";
import { useDocumentTitle } from "@/shared/lib/hooks";
import { Button, Callout, Field, Input, PasswordInput } from "@/shared/ui";

const schema = z.object({
  username: z.string().trim().min(1, "Ingrese su usuario."),
  password: z.string().min(1, "Ingrese su contraseña."),
});
type FormValues = z.infer<typeof schema>;

const HIGHLIGHTS = [
  { icon: Timer, text: "Turnos en orden de registro y cola en tiempo real" },
  { icon: Users, text: "Operación por sede con trazabilidad completa" },
  { icon: ShieldCheck, text: "Datos administrativos protegidos; sin información clínica" },
];

export default function LoginPage() {
  useDocumentTitle("Iniciar sesión");
  const { status, user, login, can } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  if (status === "loading") return <FullScreenLoader />;
  if (status === "authenticated" && user) return <Navigate to="/" replace />;

  const onSubmit = handleSubmit(async ({ username, password }) => {
    setServerError(null);
    try {
      const me = await login(username, password);
      const from = (location.state as { from?: string } | null)?.from;
      const permissions = new Set(me.permissions);
      navigate(me.must_change_password ? "/cambiar-clave" : (from ?? homeFor((p) => permissions.has(p) || can(p))), {
        replace: true,
      });
    } catch (error) {
      setServerError(errorMessage(error));
    }
  });

  return (
    <div className="grid min-h-dvh lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]">
      <section className="relative hidden overflow-hidden bg-brand-900 p-12 text-white lg:flex lg:flex-col">
        <div className="absolute inset-0 bg-[radial-gradient(80%_60%_at_10%_10%,#93263a_0%,transparent_60%),radial-gradient(60%_50%_at_90%_100%,#611824_0%,transparent_70%)]" aria-hidden />
        <div
          className="absolute inset-0 opacity-[0.07] [background-image:linear-gradient(#fff_1px,transparent_1px),linear-gradient(90deg,#fff_1px,transparent_1px)] [background-size:44px_44px]"
          aria-hidden
        />
        <div className="relative flex items-center gap-3">
          <BrandMark />
          <div className="leading-tight">
            <p className="text-xs font-medium tracking-[0.12em] text-white/60 uppercase">Poder Judicial del Perú</p>
            <p className="font-semibold">Corte Superior de Justicia de Lima</p>
          </div>
        </div>
        <div className="relative mt-auto max-w-lg">
          <p className="text-sm font-medium tracking-[0.1em] text-white/60 uppercase">Bienestar del trabajador</p>
          <h1 className="mt-3 text-4xl leading-[1.1] font-semibold tracking-tight">
            Sistema de Gestión de Atención del Tópico de Salud
          </h1>
          <p className="mt-4 text-base leading-relaxed text-white/75">
            Registro, cola y seguimiento de las atenciones de los tópicos de las sedes Javier Alzamora Valdez y Anselmo
            Barreto.
          </p>
          <ul className="mt-10 space-y-4">
            {HIGHLIGHTS.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-center gap-3 text-sm text-white/85">
                <span className="grid size-9 place-items-center rounded-lg bg-white/10 ring-1 ring-white/15">
                  <Icon className="size-4" aria-hidden />
                </span>
                {text}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <BrandMark tone="dark" />
            <div className="leading-tight">
              <p className="font-semibold">Tópico de Salud</p>
              <p className="text-xs text-ink-soft">Corte Superior de Justicia de Lima</p>
            </div>
          </div>
          <h2 className="text-2xl font-semibold tracking-tight">Iniciar sesión</h2>
          <p className="mt-1 text-sm text-ink-muted">Ingrese con el usuario asignado por la administración.</p>

          <form onSubmit={onSubmit} noValidate className="mt-8 space-y-5">
            {serverError && <Callout tone="danger">{serverError}</Callout>}
            <Field label="Usuario" error={errors.username?.message}>
              <Input autoComplete="username" autoFocus autoCapitalize="none" spellCheck={false} className="h-11" {...register("username")} />
            </Field>
            <Field label="Contraseña" error={errors.password?.message}>
              <PasswordInput autoComplete="current-password" className="h-11" {...register("password")} />
            </Field>
            <Button type="submit" size="lg" className="w-full" loading={isSubmitting} icon={<LogIn className="size-4" />}>
              Ingresar
            </Button>
          </form>

          <p className="mt-8 flex items-start gap-2 text-xs leading-relaxed text-ink-soft">
            <LockKeyhole className="mt-0.5 size-3.5 shrink-0" aria-hidden />
            Uso exclusivo del personal autorizado. Todas las acciones quedan registradas en la auditoría del sistema.
          </p>
        </div>
      </section>
    </div>
  );
}
