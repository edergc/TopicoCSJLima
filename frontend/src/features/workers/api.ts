import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/shared/api/client";
import type { Department, Page, Worker, WorkerCreateIn, WorkerSummary, WorkerUpdateIn } from "@/shared/api/types";

export function useWorkerSearch(params: { q?: string; active?: boolean; page: number; size: number }) {
  return useQuery({
    queryKey: ["workers", params],
    queryFn: ({ signal }) => api.get<Page<WorkerSummary>>("/workers", params, signal),
    placeholderData: keepPreviousData,
  });
}

/** La lectura de la ficha completa queda auditada en el backend (dato personal). */
export function useWorker(id: string | null) {
  return useQuery({
    queryKey: ["worker", id],
    queryFn: () => api.get<Worker>(`/workers/${id}`),
    enabled: Boolean(id),
    staleTime: 60_000,
  });
}

export function useDepartments() {
  return useQuery({ queryKey: ["departments"], queryFn: () => api.get<Department[]>("/catalogs/departments"), staleTime: 5 * 60_000 });
}

function useInvalidate() {
  const queryClient = useQueryClient();
  return () => {
    void queryClient.invalidateQueries({ queryKey: ["workers"] });
    void queryClient.invalidateQueries({ queryKey: ["worker"] });
    void queryClient.invalidateQueries({ queryKey: ["eligibility"] });
    void queryClient.invalidateQueries({ queryKey: ["departments"] });
  };
}

export function useCreateWorker() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (body: WorkerCreateIn) => api.post<Worker>("/workers", body), onSuccess: invalidate });
}

export function useUpdateWorker(id: string) {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (body: WorkerUpdateIn) => api.patch<Worker>(`/workers/${id}`, body), onSuccess: invalidate });
}

export function useAddCoverage(id: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: { valid_from: string; valid_to?: string | null }) => api.post<Worker>(`/workers/${id}/coverages`, body),
    onSuccess: invalidate,
  });
}

export function useEndCoverage(id: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ coverageId, ...body }: { coverageId: number; valid_to: string; end_reason: string }) =>
      api.post<Worker>(`/workers/${id}/coverages/${coverageId}/end`, body),
    onSuccess: invalidate,
  });
}
