import type { KeyboardEvent } from "react";
import { z } from "zod";

export const PASSWORD_MIN_LENGTH = 10;

/** Política de contraseña (la misma que valida el servidor). */
export const newPasswordSchema = z
  .string()
  .min(PASSWORD_MIN_LENGTH, `Debe tener al menos ${PASSWORD_MIN_LENGTH} caracteres.`)
  .regex(/[A-Za-zÁÉÍÓÚÑáéíóúñ]/, "Debe incluir letras.")
  .regex(/\d/, "Debe incluir números.");

/** Bloq Mayús activado: se avisa para evitar intentos fallidos que terminan bloqueando la cuenta. */
export function capsLockOn(event: KeyboardEvent): boolean {
  return event.getModifierState("CapsLock");
}
