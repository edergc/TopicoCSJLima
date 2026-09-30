/**
 * Tipos de la API derivados del OpenAPI del backend (schema.d.ts se genera con `npm run gen:api`).
 * Si el backend cambia un contrato, TypeScript señala cada uso afectado.
 */
import type { components } from "./schema";

type S = components["schemas"];

export type Me = S["MeOut"];
export type TokenResponse = S["TokenOut"];
export type SiteRef = S["SiteRef"];
export type Site = S["SiteOut"];
export type Availability = S["AvailabilityOut"];
export type SiteSettings = S["SiteSettingsOut"];
export type SettingVersion = S["SettingVersionOut"];
export type SettingVersionIn = S["SettingVersionIn"];
export type ScheduleRow = S["ScheduleRowOut"];
export type ScheduleIn = S["ScheduleIn"];
export type Closure = S["ClosureOut"];

export type Eligibility = S["EligibilityOut"];
export type WorkerSummary = S["WorkerSummaryOut"];
export type Worker = S["WorkerOut"];
export type WorkerCreateIn = S["WorkerCreateIn"];
export type WorkerUpdateIn = S["WorkerUpdateIn"];
export type Department = S["DepartmentOut"];

export type Appointment = S["AppointmentOut"];
export type AppointmentCreateIn = S["AppointmentCreateIn"];
export type TransitionIn = S["TransitionIn"];
export type Queue = S["QueueOut"];
export type QueueCounts = S["QueueCountsOut"];
export type Incident = S["IncidentOut"];
export type AppointmentEvent = S["AppointmentEventOut"];
export type NotificationItem = S["NotificationOut"];
export type Reason = S["ReasonOut"];
export type AppointmentStatusInfo = S["StatusOut"];

export type ImportBatch = S["ImportBatchOut"];
export type ImportRow = S["ImportRowOut"];

export type AuditEvent = S["AuditEventOut"];
export type ChainVerification = S["ChainVerificationOut"];

export type User = S["UserOut"];
export type UserWithPassword = S["UserWithPasswordOut"];
export type UserCreateIn = S["UserCreateIn"];
export type UserUpdateIn = S["UserUpdateIn"];
export type Role = S["RoleOut"];
export type Permission = S["PermissionOut"];
export type Parameter = S["ParameterOut"];
export type ReasonAdmin = S["ReasonAdminOut"];
export type Template = S["TemplateOut"];
export type TemplatePreview = S["TemplatePreviewOut"];
export type PublicTicketStatus = S["PublicTicketStatusOut"];

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}

export type AppointmentStatus =
  | "REGISTRADO"
  | "EN_ESPERA"
  | "LLAMADO"
  | "EN_ATENCION"
  | "ATENDIDO"
  | "CANCELADO"
  | "NO_PRESENTADO"
  | "ANULADO";

export type AppointmentAction = "CALL" | "START" | "FINISH" | "REQUEUE" | "NO_SHOW" | "CANCEL" | "VOID";
