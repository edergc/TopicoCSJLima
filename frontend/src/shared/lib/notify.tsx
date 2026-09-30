import { toast } from "sonner";

import { ApiError } from "@/shared/api/client";

/**
 * Notificaciones al usuario. Los errores de la API ya traen un mensaje comprensible en
 * español (código estable + mensaje); aquí solo se decide cómo mostrarlos.
 */
export const notify = {
  success: (title: string, description?: string) => toast.success(title, { description }),
  info: (title: string, description?: string) => toast.info(title, { description }),
  warning: (title: string, description?: string) => toast.warning(title, { description }),
  error: (error: unknown, fallback = "No se pudo completar la operación") => {
    if (error instanceof ApiError) {
      const details = error.fieldErrors.length
        ? error.fieldErrors.map((f) => `${f.field ? `${f.field}: ` : ""}${f.message}`).join(" · ")
        : Array.isArray(error.details)
          ? (error.details as string[]).join(" · ")
          : undefined;
      toast.error(error.message, {
        description: details ?? (error.status >= 500 && error.requestId ? `Código de solicitud: ${error.requestId}` : undefined),
      });
      return;
    }
    toast.error(fallback);
  },
};

export function errorMessage(error: unknown, fallback = "Ocurrió un error inesperado."): string {
  return error instanceof ApiError ? error.message : fallback;
}

export function errorCode(error: unknown): string | null {
  return error instanceof ApiError ? error.code : null;
}
