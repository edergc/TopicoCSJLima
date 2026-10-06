import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, api } from "@/shared/api/client";
import type {
  Appointment,
  AppointmentAction,
  AppointmentCreateIn,
  AppointmentEvent,
  Availability,
  Doctor,
  Eligibility,
  NotificationItem,
  Page,
  Queue,
  Reason,
  Room,
  TransitionIn,
} from "@/shared/api/types";
import { notify } from "@/shared/lib/notify";
import { syncServerTime } from "@/shared/lib/serverTime";

export const keys = {
  queue: (siteId: number) => ["queue", siteId] as const,
  availability: (siteId: number) => ["availability", siteId] as const,
  eligibility: (dni: string) => ["eligibility", dni] as const,
  reasons: (type: string) => ["reasons", type] as const,
  appointment: (id: string) => ["appointment", id] as const,
  events: (id: string) => ["appointment", id, "events"] as const,
  notifications: (id: string) => ["appointment", id, "notifications"] as const,
  search: (params: object) => ["appointments", params] as const,
  doctors: (siteId: number) => ["doctors", siteId] as const,
  rooms: (siteId: number) => ["rooms", siteId] as const,
};

const QUEUE_REFRESH_MS = 5_000;

/** Cola del día. Se actualiza cada 5 s mientras la pestaña está visible. */
export function useQueue(siteId: number | undefined) {
  return useQuery({
    queryKey: keys.queue(siteId ?? 0),
    queryFn: async ({ signal }) => {
      const sentAt = Date.now();
      const queue = await api.get<Queue>(`/sites/${siteId}/queue`, undefined, signal);
      syncServerTime(queue.generated_at, (sentAt + Date.now()) / 2);
      return queue;
    },
    enabled: Boolean(siteId),
    refetchInterval: QUEUE_REFRESH_MS,
    refetchIntervalInBackground: false,
    staleTime: 2_000,
    placeholderData: keepPreviousData,
  });
}

export function useAvailability(siteId: number | undefined) {
  return useQuery({
    queryKey: keys.availability(siteId ?? 0),
    queryFn: ({ signal }) => api.get<Availability>(`/sites/${siteId}/availability`, undefined, signal),
    enabled: Boolean(siteId),
    refetchInterval: 30_000,
  });
}

export function useEligibility(dni: string) {
  return useQuery({
    queryKey: keys.eligibility(dni),
    queryFn: ({ signal }) => api.get<Eligibility>("/workers/eligibility", { document_number: dni }, signal),
    enabled: /^\d{8}$/.test(dni),
    staleTime: 10_000,
    retry: false,
  });
}

export function useReasons(type: string) {
  return useQuery({
    queryKey: keys.reasons(type),
    queryFn: () => api.get<Reason[]>("/catalogs/reasons", { type }),
    staleTime: 5 * 60_000,
  });
}

function useInvalidateOperation() {
  const queryClient = useQueryClient();
  return (siteId?: number) => {
    void queryClient.invalidateQueries({ queryKey: siteId ? keys.queue(siteId) : ["queue"] });
    void queryClient.invalidateQueries({ queryKey: siteId ? keys.availability(siteId) : ["availability"] });
    void queryClient.invalidateQueries({ queryKey: ["eligibility"] });
    void queryClient.invalidateQueries({ queryKey: ["appointment"] });
    void queryClient.invalidateQueries({ queryKey: ["appointments"] });
  };
}

export function useRegisterAppointment() {
  const invalidate = useInvalidateOperation();
  return useMutation({
    mutationFn: (body: AppointmentCreateIn) => api.post<Appointment>("/appointments", body),
    onSettled: (_data, _error, body) => invalidate(body.site_id),
  });
}

const ACTION_PATH: Record<AppointmentAction, string> = {
  CALL: "call",
  START: "start",
  FINISH: "finish",
  REQUEUE: "requeue",
  NO_SHOW: "no-show",
  CANCEL: "cancel",
  VOID: "void",
};

export interface TransitionVars {
  appointment: Pick<Appointment, "public_id" | "site_id" | "version">;
  action: AppointmentAction;
  body?: Omit<TransitionIn, "version">;
}

export function useTransition() {
  const invalidate = useInvalidateOperation();
  return useMutation({
    mutationFn: ({ appointment, action, body }: TransitionVars) =>
      api.post<Appointment>(`/appointments/${appointment.public_id}/${ACTION_PATH[action]}`, {
        ...body,
        version: appointment.version,
      }),
    onError: (error) => {
      if (error instanceof ApiError && error.code === "APPOINTMENT_CHANGED") {
        notify.warning("La atención cambió", "Otro usuario la modificó. Se actualizó la información.");
      } else {
        notify.error(error);
      }
    },
    onSettled: (_data, _error, vars) => invalidate(vars.appointment.site_id),
  });
}

export function useCallNext(siteId: number | undefined) {
  const invalidate = useInvalidateOperation();
  return useMutation({
    mutationFn: (roomId?: number | null) =>
      api.post<Appointment>(`/sites/${siteId}/queue/call-next`, roomId ? { room_id: roomId } : undefined),
    onSettled: () => invalidate(siteId),
  });
}

export function useAppointment(id: string | null) {
  return useQuery({
    queryKey: keys.appointment(id ?? ""),
    queryFn: () => api.get<Appointment>(`/appointments/${id}`),
    enabled: Boolean(id),
  });
}

export function useAppointmentEvents(id: string | null) {
  return useQuery({
    queryKey: keys.events(id ?? ""),
    queryFn: () => api.get<AppointmentEvent[]>(`/appointments/${id}/events`),
    enabled: Boolean(id),
  });
}

export function useAppointmentNotifications(id: string | null, enabled = true) {
  return useQuery({
    queryKey: keys.notifications(id ?? ""),
    queryFn: () => api.get<NotificationItem[]>(`/appointments/${id}/notifications`),
    enabled: Boolean(id) && enabled,
  });
}

export function useResendNotification() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (notificationId: number) => api.post<NotificationItem>(`/notifications/${notificationId}/resend`),
    onSuccess: () => {
      notify.success("Notificación reenviada", "Se enviará en los próximos segundos.");
      void queryClient.invalidateQueries({ queryKey: ["appointment"] });
    },
    onError: (error) => notify.error(error),
  });
}

export interface AppointmentSearch {
  site_id?: number;
  date_from?: string;
  date_to?: string;
  status?: string;
  document_number?: string;
  page: number;
  size: number;
}

export function useAppointmentSearch(params: AppointmentSearch) {
  return useQuery({
    queryKey: keys.search(params),
    queryFn: ({ signal }) => api.get<Page<Appointment>>("/appointments", { ...params }, signal),
    placeholderData: keepPreviousData,
  });
}

/** Médicos de la sede (todos; la mesa filtra los activos). */
export function useDoctors(siteId: number | undefined) {
  return useQuery({
    queryKey: keys.doctors(siteId ?? 0),
    queryFn: () => api.get<Doctor[]>(`/sites/${siteId}/doctors`),
    enabled: siteId !== undefined,
    staleTime: 60_000,
  });
}

/** Consultorios de la sede (todos; la mesa filtra los activos). */
export function useRooms(siteId: number | undefined) {
  return useQuery({
    queryKey: keys.rooms(siteId ?? 0),
    queryFn: () => api.get<Room[]>(`/sites/${siteId}/rooms`),
    enabled: siteId !== undefined,
    staleTime: 60_000,
  });
}
