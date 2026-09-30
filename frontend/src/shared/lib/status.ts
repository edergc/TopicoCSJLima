import {
  Ban,
  BellRing,
  CheckCircle2,
  CircleSlash,
  ClipboardList,
  Hourglass,
  Stethoscope,
  XCircle,
  type LucideIcon,
} from "lucide-react";

import type { AppointmentAction, AppointmentStatus } from "@/shared/api/types";

/**
 * Semántica visual de los estados (sección 39 del requerimiento):
 * cada estado tiene texto + ícono + color; nunca se depende solo del color.
 */
export interface StatusStyle {
  label: string;
  icon: LucideIcon;
  text: string;
  bg: string;
  ring: string;
  dot: string;
}

export const STATUS: Record<AppointmentStatus, StatusStyle> = {
  REGISTRADO: {
    label: "Registrado",
    icon: ClipboardList,
    text: "text-status-registered",
    bg: "bg-status-registered-bg",
    ring: "ring-status-registered/20",
    dot: "bg-status-registered",
  },
  EN_ESPERA: {
    label: "En espera",
    icon: Hourglass,
    text: "text-status-waiting",
    bg: "bg-status-waiting-bg",
    ring: "ring-status-waiting/25",
    dot: "bg-status-waiting",
  },
  LLAMADO: {
    label: "Llamado",
    icon: BellRing,
    text: "text-status-called",
    bg: "bg-status-called-bg",
    ring: "ring-status-called/25",
    dot: "bg-status-called",
  },
  EN_ATENCION: {
    label: "En atención",
    icon: Stethoscope,
    text: "text-status-inservice",
    bg: "bg-status-inservice-bg",
    ring: "ring-status-inservice/25",
    dot: "bg-status-inservice",
  },
  ATENDIDO: {
    label: "Atendido",
    icon: CheckCircle2,
    text: "text-status-done",
    bg: "bg-status-done-bg",
    ring: "ring-status-done/25",
    dot: "bg-status-done",
  },
  CANCELADO: {
    label: "Cancelado",
    icon: XCircle,
    text: "text-status-cancelled",
    bg: "bg-status-cancelled-bg",
    ring: "ring-status-cancelled/20",
    dot: "bg-status-cancelled",
  },
  NO_PRESENTADO: {
    label: "No presentado",
    icon: CircleSlash,
    text: "text-status-noshow",
    bg: "bg-status-noshow-bg",
    ring: "ring-status-noshow/20",
    dot: "bg-status-noshow",
  },
  ANULADO: {
    label: "Anulado",
    icon: Ban,
    text: "text-status-cancelled",
    bg: "bg-status-cancelled-bg",
    ring: "ring-status-cancelled/20",
    dot: "bg-status-cancelled",
  },
};

export function statusStyle(status: string): StatusStyle {
  return STATUS[status as AppointmentStatus] ?? STATUS.REGISTRADO;
}

export const ACTION_LABEL: Record<AppointmentAction, string> = {
  CALL: "Llamar",
  START: "Iniciar atención",
  FINISH: "Finalizar",
  REQUEUE: "Devolver a la cola",
  NO_SHOW: "No se presentó",
  CANCEL: "Cancelar",
  VOID: "Anular",
};

export const CHANNEL_LABEL: Record<string, string> = {
  PHONE: "Teléfono",
  WALK_IN: "Presencial",
  WEB: "Web",
  MIGRATION: "Histórico",
};
