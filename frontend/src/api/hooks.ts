import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  AiFunction,
  AnalysisRun,
  api,
  Review,
  ReviewSource,
  ScrapeJob,
  Store,
  Workspace,
} from "./client";

// ─── Workspaces ─────────────────────────────────────────────────────
export function useWorkspaces() {
  return useQuery({
    queryKey: ["workspaces"],
    queryFn: async () => (await api.get<Workspace[]>("/workspaces")).data,
  });
}

export function useCreateWorkspace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (name: string) =>
      (await api.post<Workspace>("/workspaces", { name })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["workspaces"] }),
  });
}

// ─── Stores ─────────────────────────────────────────────────────────
export function useStores(workspaceId?: number) {
  return useQuery({
    queryKey: ["stores", workspaceId],
    queryFn: async () => {
      const params = workspaceId ? { workspace_id: workspaceId } : {};
      return (await api.get<Store[]>("/stores", { params })).data;
    },
  });
}

export function useStore(storeId: number) {
  return useQuery({
    queryKey: ["stores", storeId],
    queryFn: async () => (await api.get<Store>(`/stores/${storeId}`)).data,
    enabled: storeId > 0,
  });
}

export function useCreateStore() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: {
      workspace_id: number;
      name: string;
      address?: string;
      primary_url?: string;
      platform?: "google" | "youtube";
    }) => (await api.post<Store>("/stores", body)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["stores"] }),
  });
}

// ─── Sources ────────────────────────────────────────────────────────
export function useAddSource(storeId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: {
      source_type: "google_maps" | "youtube";
      external_url: string;
    }) =>
      (
        await api.post<ReviewSource>(`/stores/${storeId}/sources`, body)
      ).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["stores", storeId] }),
  });
}

// ─── Scrape jobs ────────────────────────────────────────────────────
export function useFireScrape(storeId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      (await api.post<ScrapeJob>(`/stores/${storeId}/scrape`, {})).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["stores"] }),
  });
}

export function useJob(jobId: number, refetchInterval = 2000) {
  return useQuery({
    queryKey: ["jobs", jobId],
    queryFn: async () => (await api.get<ScrapeJob>(`/jobs/${jobId}`)).data,
    enabled: jobId > 0,
    refetchInterval: (q) => {
      const data = q.state.data as ScrapeJob | undefined;
      if (!data) return refetchInterval;
      if (["succeeded", "failed", "cancelled"].includes(data.status))
        return false;
      return refetchInterval;
    },
  });
}

// ─── Reviews ───────────────────────────────────────────────────────
export function useReviews(storeId: number, limit = 100) {
  return useQuery({
    queryKey: ["reviews", storeId, limit],
    queryFn: async () =>
      (
        await api.get<Review[]>(`/stores/${storeId}/reviews`, {
          params: { limit },
        })
      ).data,
    enabled: storeId > 0,
  });
}

// ─── Analysis runs ─────────────────────────────────────────────────
export function useAnalysisRuns(storeId: number) {
  return useQuery({
    queryKey: ["runs", storeId],
    queryFn: async () =>
      (await api.get<AnalysisRun[]>(`/stores/${storeId}/runs`)).data,
    enabled: storeId > 0,
  });
}

export function useFireAnalysis(storeId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: {
      ai_function: AiFunction;
      inputs?: Record<string, unknown>;
      model_tier?: "standard" | "premium";
    }) =>
      (
        await api.post<AnalysisRun>(`/stores/${storeId}/analyze`, body)
      ).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["runs", storeId] }),
  });
}

export function useAnalysisRun(runId: number, refetchInterval = 2000) {
  return useQuery({
    queryKey: ["run", runId],
    queryFn: async () => (await api.get<AnalysisRun>(`/runs/${runId}`)).data,
    enabled: runId > 0,
    refetchInterval: (q) => {
      const data = q.state.data as AnalysisRun | undefined;
      if (!data) return refetchInterval;
      if (["succeeded", "failed", "cancelled"].includes(data.status))
        return false;
      return refetchInterval;
    },
  });
}
