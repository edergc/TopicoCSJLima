import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/shared/api/client";
import type {
  Page,
  Parameter,
  Permission,
  ReasonAdmin,
  Role,
  Site,
  Template,
  TemplatePreview,
  User,
  UserCreateIn,
  UserUpdateIn,
  UserWithPassword,
} from "@/shared/api/types";

export function useUsers(params: { q?: string; active?: boolean; page: number; size: number }) {
  return useQuery({
    queryKey: ["admin-users", params],
    queryFn: () => api.get<Page<User>>("/admin/users", params),
    placeholderData: keepPreviousData,
  });
}

export function useRoles() {
  return useQuery({ queryKey: ["admin-roles"], queryFn: () => api.get<Role[]>("/admin/roles") });
}

export function usePermissions() {
  return useQuery({ queryKey: ["admin-permissions"], queryFn: () => api.get<Permission[]>("/admin/permissions"), staleTime: Infinity });
}

export function useAllSites() {
  return useQuery({ queryKey: ["sites"], queryFn: () => api.get<Site[]>("/sites"), staleTime: 60_000 });
}

function useInvalidate(...keys: string[]) {
  const queryClient = useQueryClient();
  return () => keys.forEach((key) => void queryClient.invalidateQueries({ queryKey: [key] }));
}

export function useCreateUser() {
  const invalidate = useInvalidate("admin-users");
  return useMutation({ mutationFn: (body: UserCreateIn) => api.post<UserWithPassword>("/admin/users", body), onSuccess: invalidate });
}

export function useUpdateUser() {
  const invalidate = useInvalidate("admin-users");
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: UserUpdateIn }) => api.patch<User>(`/admin/users/${id}`, body),
    onSuccess: invalidate,
  });
}

export function useResetPassword() {
  const invalidate = useInvalidate("admin-users");
  return useMutation({ mutationFn: (id: string) => api.post<UserWithPassword>(`/admin/users/${id}/reset-password`), onSuccess: invalidate });
}

export function useUnlockUser() {
  const invalidate = useInvalidate("admin-users");
  return useMutation({ mutationFn: (id: string) => api.post<User>(`/admin/users/${id}/unlock`), onSuccess: invalidate });
}

export function useSetRolePermissions() {
  const invalidate = useInvalidate("admin-roles");
  return useMutation({
    mutationFn: ({ roleId, codes }: { roleId: number; codes: string[] }) =>
      api.put<Role>(`/admin/roles/${roleId}/permissions`, { permission_codes: codes }),
    onSuccess: invalidate,
  });
}

export function useParameters() {
  return useQuery({ queryKey: ["admin-parameters"], queryFn: () => api.get<Parameter[]>("/admin/parameters") });
}

export function useUpdateParameter() {
  const invalidate = useInvalidate("admin-parameters");
  return useMutation({
    mutationFn: ({ key, value }: { key: string; value: unknown }) => api.put<Parameter>(`/admin/parameters/${key}`, { value }),
    onSuccess: invalidate,
  });
}

export function useAdminReasons() {
  return useQuery({ queryKey: ["admin-reasons"], queryFn: () => api.get<ReasonAdmin[]>("/admin/reasons") });
}

export function useSaveReason() {
  const invalidate = useInvalidate("admin-reasons", "reasons");
  return useMutation({
    mutationFn: ({ id, body }: { id?: number; body: Record<string, unknown> }) =>
      id ? api.patch<ReasonAdmin>(`/admin/reasons/${id}`, body) : api.post<ReasonAdmin>("/admin/reasons", body),
    onSuccess: invalidate,
  });
}

export function useTemplates() {
  return useQuery({ queryKey: ["admin-templates"], queryFn: () => api.get<Template[]>("/admin/notification-templates") });
}

export function useSaveTemplate() {
  const invalidate = useInvalidate("admin-templates", "template-preview");
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: Record<string, unknown> }) => api.patch<Template>(`/admin/notification-templates/${id}`, body),
    onSuccess: invalidate,
  });
}

export function useTemplatePreview(id: number | null) {
  return useQuery({
    queryKey: ["template-preview", id],
    queryFn: () => api.get<TemplatePreview>(`/admin/notification-templates/${id}/preview`),
    enabled: id !== null,
  });
}
