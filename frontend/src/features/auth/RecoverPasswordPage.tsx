import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, KeyRound, MailCheck, Send } from "lucide-react";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { z } from "zod";

import { ApiError, api } from "@/shared/api/client";
import { useDocumentTitle } from "@/shared/lib/hooks";
import { errorMessage } from "@/shared/lib/notify";
import { DniInput, Button, Callout, Field, PasswordInput } from "@/shared/ui";

import { AuthLayout } from "./AuthLayout";
import type { LoginNotice } from "./LoginPage";
import { newPasswordSchema } from "./password";
import { PasswordRules } from "./PasswordRules";

function readToken(): string {
  const token = window.location.hash.slice(1);
  if (token) window.history.replaceState(null, "", window.location.pathname); // el enlace no queda en el historial
  return token;
}

function BackToLogin() {
  return (
    <Link to="/login" className="mt-6 inline-flex items-center gap-1.5 text-sm font-medium text-brand-700 hover:underline">
      <ArrowLeft className="size-4" aria-hidden /> Volver a iniciar sesión
    </Link>
  );
}

/** Recuperar la contraseña: pedir el enlace por correo y, con el enlace, definir una nueva. */
export default function RecoverPasswordPage() {
  const [token, setToken] = useState(readToken);
  useDocumentTitle(token ? "Nueva contraseña" : "Recuperar contraseña");
  return token ? <ResetForm token={token} onRestart={() => setToken("")} /> : <RequestForm />;
}

const requestSchema = z.object({
  username: z.string().trim().regex(/^[0-9]{8}$/, "Su usuario es su DNI: 8 dígitos, solo números."),
});

function RequestForm() {
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<z.infer<typeof requestSchema>>({
    resolver: zodResolver(requestSchema),
  });

  const onSubmit = handleSubmit(async ({ username }) => {
    setServerError(null);
    try {
      await api.post("/auth/password-reset/request", { username }, { skipRefresh: true });
      setSentTo(username);
    } catch (error) {
      setServerError(errorMessage(error));
    }
  });

  if (sentTo) {
    return (
      <AuthLayout title="Revise su correo">
        <div className="flex gap-3 rounded-xl border border-line bg-sunken/60 p-4">
          <MailCheck className="mt-0.5 size-5 shrink-0 text-success" aria-hidden />
          <div className="space-y-2 text-sm leading-relaxed text-ink-muted">
            <p>
              Si el usuario <strong className="text-ink">{sentTo}</strong> tiene un correo registrado, en unos minutos recibirá un
              enlace para definir una nueva contraseña. El enlace vence pronto y sirve una sola vez.
            </p>
            <p>Revise también la carpeta de correo no deseado.</p>
          </div>
        </div>
        <Callout tone="info" className="mt-4" title="¿No le llegó el correo?">
          Es posible que su usuario no tenga correo registrado. Pida al administrador del sistema que restablezca su contraseña.
        </Callout>
        <BackToLogin />
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      title="Recuperar contraseña"
      subtitle="Ingrese su usuario y le enviaremos un enlace al correo registrado para que defina una nueva contraseña."
    >
      <form onSubmit={onSubmit} noValidate className="space-y-5">
        {serverError && <Callout tone="danger">{serverError}</Callout>}
        <Field label="Usuario (DNI)" error={errors.username?.message}>
          <DniInput
            autoComplete="username"
            autoFocus
            autoCapitalize="none"
            spellCheck={false}
            className="h-11"
            {...register("username")}
          />
        </Field>
        <Button type="submit" size="lg" className="w-full" loading={isSubmitting} icon={<Send className="size-4" />}>
          Enviar enlace
        </Button>
      </form>
      <BackToLogin />
    </AuthLayout>
  );
}

const resetSchema = z
  .object({ new_password: newPasswordSchema, confirm: z.string() })
  .refine((v) => v.new_password === v.confirm, {
    path: ["confirm"],
    message: "Las contraseñas no coinciden.",
  });

const LINK_ERRORS = new Set(["RESET_LINK_INVALID", "RESET_LINK_EXPIRED"]);

function ResetForm({ token, onRestart }: { token: string; onRestart: () => void }) {
  const navigate = useNavigate();
  const [serverError, setServerError] = useState<{
    message: string;
    linkProblem: boolean;
  } | null>(null);
  const {
    register,
    handleSubmit,
    control,
    formState: { errors, isSubmitting },
  } = useForm<z.infer<typeof resetSchema>>({
    resolver: zodResolver(resetSchema),
    defaultValues: { new_password: "", confirm: "" },
  });
  const value = useWatch({ control, name: "new_password" });

  const onSubmit = handleSubmit(async ({ new_password }) => {
    setServerError(null);
    try {
      await api.post("/auth/password-reset/confirm", { token, new_password }, { skipRefresh: true });
      const state: LoginNotice = {
        notice: "Su contraseña se actualizó. Ingrese con su nueva contraseña.",
      };
      navigate("/login", { replace: true, state });
    } catch (error) {
      setServerError({
        message: errorMessage(error),
        linkProblem: error instanceof ApiError && LINK_ERRORS.has(error.code),
      });
    }
  });

  if (serverError?.linkProblem) {
    return (
      <AuthLayout title="Enlace no válido">
        <Callout tone="warning">{serverError.message}</Callout>
        <Button size="lg" className="mt-5 w-full" icon={<Send className="size-4" />} onClick={onRestart}>
          Solicitar un nuevo enlace
        </Button>
        <BackToLogin />
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Defina su nueva contraseña" subtitle="Al guardarla se cerrarán las sesiones abiertas con su usuario.">
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        {serverError && <Callout tone="danger">{serverError.message}</Callout>}
        <Field label="Nueva contraseña" error={errors.new_password?.message}>
          <PasswordInput autoComplete="new-password" autoFocus className="h-11" {...register("new_password")} />
        </Field>
        <PasswordRules value={value} />
        <Field label="Confirmar nueva contraseña" error={errors.confirm?.message}>
          <PasswordInput autoComplete="new-password" className="h-11" {...register("confirm")} />
        </Field>
        <Button type="submit" size="lg" className="w-full" loading={isSubmitting} icon={<KeyRound className="size-4" />}>
          Guardar contraseña
        </Button>
      </form>
      <BackToLogin />
    </AuthLayout>
  );
}
