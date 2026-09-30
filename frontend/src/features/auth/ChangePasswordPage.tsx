import { zodResolver } from "@hookform/resolvers/zod";
import { Check, KeyRound, X } from "lucide-react";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { z } from "zod";

import { BrandMark } from "@/app/layout/BrandMark";
import { homeFor } from "@/app/navigation";
import { api } from "@/shared/api/client";
import type { TokenResponse } from "@/shared/api/types";
import { useAuth, useUser } from "@/shared/auth/AuthProvider";
import { cn } from "@/shared/lib/cn";
import { useDocumentTitle } from "@/shared/lib/hooks";
import { errorMessage, notify } from "@/shared/lib/notify";
import { Button, Callout, Card, Field, Input } from "@/shared/ui";

const MIN_LENGTH = 10;

const schema = z
  .object({
    current_password: z.string().min(1, "Ingrese su contraseña actual."),
    new_password: z
      .string()
      .min(MIN_LENGTH, `Debe tener al menos ${MIN_LENGTH} caracteres.`)
      .regex(/[A-Za-zÁÉÍÓÚÑáéíóúñ]/, "Debe incluir letras.")
      .regex(/\d/, "Debe incluir números."),
    confirm: z.string(),
  })
  .refine((v) => v.new_password === v.confirm, { path: ["confirm"], message: "Las contraseñas no coinciden." });
type FormValues = z.infer<typeof schema>;

export default function ChangePasswordPage() {
  useDocumentTitle("Cambiar contraseña");
  const user = useUser();
  const { applyToken, can } = useAuth();
  const navigate = useNavigate();
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    control,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { current_password: "", new_password: "", confirm: "" } });
  const value = useWatch({ control, name: "new_password" });

  const rules = [
    { ok: value.length >= MIN_LENGTH, text: `Al menos ${MIN_LENGTH} caracteres` },
    { ok: /[A-Za-z]/.test(value) && /\d/.test(value), text: "Letras y números" },
    { ok: value.length > 0 && !value.toLowerCase().includes(user.username.toLowerCase()), text: "Sin su nombre de usuario" },
  ];

  const onSubmit = handleSubmit(async ({ current_password, new_password }) => {
    setServerError(null);
    try {
      const token = await api.post<TokenResponse>("/auth/change-password", { current_password, new_password });
      applyToken(token);
      notify.success("Contraseña actualizada", "Se cerraron las demás sesiones abiertas con su usuario.");
      const permissions = new Set(token.user.permissions);
      navigate(homeFor((p) => permissions.has(p) || can(p)), { replace: true });
    } catch (error) {
      setServerError(errorMessage(error));
    }
  });

  return (
    <div className="grid min-h-dvh place-items-center px-4 py-10">
      <Card className="w-full max-w-md p-8">
        <div className="flex items-center gap-3">
          <BrandMark tone="dark" />
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Cambiar contraseña</h1>
            <p className="text-sm text-ink-muted">{user.full_name}</p>
          </div>
        </div>
        {user.must_change_password && (
          <Callout tone="warning" className="mt-6" title="Debe definir una contraseña personal">
            Su contraseña actual es temporal. Por seguridad, cámbiela antes de continuar.
          </Callout>
        )}
        <form onSubmit={onSubmit} noValidate className="mt-6 space-y-4">
          {serverError && <Callout tone="danger">{serverError}</Callout>}
          <Field label="Contraseña actual" error={errors.current_password?.message}>
            <Input type="password" autoComplete="current-password" autoFocus {...register("current_password")} />
          </Field>
          <Field label="Nueva contraseña" error={errors.new_password?.message}>
            <Input type="password" autoComplete="new-password" {...register("new_password")} />
          </Field>
          <ul className="grid gap-1.5 text-[13px]" aria-label="Requisitos de la contraseña">
            {rules.map((rule) => (
              <li key={rule.text} className={cn("flex items-center gap-2", rule.ok ? "text-success" : "text-ink-soft")}>
                {rule.ok ? <Check className="size-3.5" aria-hidden /> : <X className="size-3.5" aria-hidden />}
                {rule.text}
              </li>
            ))}
          </ul>
          <Field label="Confirmar nueva contraseña" error={errors.confirm?.message}>
            <Input type="password" autoComplete="new-password" {...register("confirm")} />
          </Field>
          <Button type="submit" size="lg" className="w-full" loading={isSubmitting} icon={<KeyRound className="size-4" />}>
            Guardar contraseña
          </Button>
        </form>
      </Card>
    </div>
  );
}
