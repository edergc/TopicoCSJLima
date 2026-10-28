import { Check, X } from "lucide-react";

import { cn } from "@/shared/lib/cn";

import { PASSWORD_MIN_LENGTH } from "./password";

/** Lista de requisitos que se marca a medida que se escribe la nueva contraseña. */
export function PasswordRules({ value, username }: { value: string; username?: string }) {
  const rules = [
    {
      ok: value.length >= PASSWORD_MIN_LENGTH,
      text: `Al menos ${PASSWORD_MIN_LENGTH} caracteres`,
    },
    {
      ok: /[A-Za-zÁÉÍÓÚÑáéíóúñ]/.test(value) && /\d/.test(value),
      text: "Letras y números",
    },
    ...(username
      ? [
          {
            ok: value.length > 0 && !value.toLowerCase().includes(username.toLowerCase()),
            text: "Sin su nombre de usuario",
          },
        ]
      : []),
  ];
  return (
    <ul className="grid gap-1.5 text-[0.8125rem]" aria-label="Requisitos de la contraseña">
      {rules.map((rule) => (
        <li key={rule.text} className={cn("flex items-center gap-2", rule.ok ? "text-success" : "text-ink-soft")}>
          {rule.ok ? <Check className="size-3.5" aria-hidden /> : <X className="size-3.5" aria-hidden />}
          {rule.text}
        </li>
      ))}
    </ul>
  );
}
