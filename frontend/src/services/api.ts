/** REST client for Nexus AI Engine (spec 060, 070). */

import { normalizeStageJob, normalizeStageJourneyDetail } from "@/lib/stageJourney";
import type {
  DslJourneySummary,
  JourneyListResponse,
  ExecutionGraph,
  ExecutionNodeState,
  ExecutionSummary,
  FleetMetrics,
  FleetSummary,
  FleetWorker,
  QueueJobsResponse,
  QueueSummary,
  ScheduleRow,
  ToolDescriptor,
  ValidationResult,
  WorkerRow,
  WorkersSummary,
} from "@/types/api";
import type { RegisteredStage, StageJob, StageJourneyDetail, UnifiedRunRow } from "@/types/stageJourney";
import { authStore } from "@/services/authStore";

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";

type FetchOpts = {
  method?: string;
  body?: unknown;
  rawBody?: string;
  query?: Record<string, string | number | undefined | null>;
  headers?: Record<string, string>;
};

export async function apiFetch<T>(path: string, opts: FetchOpts = {}): Promise<T> {
  const url = new URL(`${API_BASE || window.location.origin}${path}`);
  if (opts.query) {
    for (const [k, v] of Object.entries(opts.query)) {
      if (v !== undefined && v !== null) url.searchParams.set(k, String(v));
    }
  }
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(opts.rawBody ? {} : opts.body ? { "Content-Type": "application/json" } : {}),
    ...opts.headers,
  };
  const user = authStore.get();
  if (user?.access_token) headers.Authorization = `Bearer ${user.access_token}`;

  const res = await fetch(url.toString(), {
    method: opts.method ?? "GET",
    headers,
    ...(opts.rawBody ? { body: opts.rawBody } : opts.body ? { body: JSON.stringify(opts.body) } : {}),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${opts.method ?? "GET"} ${path} failed: ${res.status} ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  version: () => apiFetch<{ version: string }>("/version"),

  listExecutions: (query?: Record<string, string>) =>
    apiFetch<ExecutionSummary[]>("/api/v1/executions/", { query }),

  getExecution: (id: string) => apiFetch<Record<string, unknown>>(`/api/v1/executions/${id}`),

  listExecutionNodes: (id: string) =>
    apiFetch<ExecutionNodeState[]>(`/api/v1/executions/${id}/nodes`),

  getExecutionGraph: (id: string) =>
    apiFetch<ExecutionGraph>(`/api/v1/executions/${id}/graph`),

  submitExecution: (body: {
    journey_id: string;
    journey_version?: number;
    mode?: string;
    labels?: Record<string, string>;
  }) =>
    apiFetch<{ execution_id: string; status: string }>("/api/v1/executions/", {
      method: "POST",
      body,
    }),

  cancelExecution: (id: string) =>
    apiFetch<{ execution_id: string; status: string }>(`/api/v1/executions/${id}/cancel`, {
      method: "POST",
    }),

  listDslJourneys: () => apiFetch<DslJourneySummary[]>("/api/v1/journeys/dsl"),

  listSimpleJourneys: () =>
    apiFetch<JourneyListResponse>("/api/v1/journeys/").then((r) => r.data),

  listRegisteredStages: () =>
    apiFetch<{ count: number; stages: RegisteredStage[] }>("/api/v1/stages/registered").then(
      (r) => r.stages ?? [],
    ),

  getStageJourney: async (journeyId: string): Promise<StageJourneyDetail> => {
    const [raw, registry] = await Promise.all([
      apiFetch<unknown>(`/api/v1/journeys/${journeyId}`),
      api.listRegisteredStages().catch(() => [] as RegisteredStage[]),
    ]);
    return normalizeStageJourneyDetail(raw, journeyId, registry);
  },

  listJourneyJobs: async (journeyId: string): Promise<StageJob[]> => {
    const raw = await apiFetch<{ jobs?: unknown[] }>(`/api/v1/journeys/${journeyId}/jobs`);
    const jobs = Array.isArray(raw) ? raw : (raw.jobs ?? []);
    return jobs.map((job) => normalizeStageJob(job, { journeyId }));
  },

  runJourneyJob: async (journeyId: string) => {
    const raw = await apiFetch<unknown>(`/api/v1/journeys/${journeyId}/jobs?triggered_by=ui`, {
      method: "POST",
      body: { triggered_by: "ui" },
    });
    return normalizeStageJob(raw, { journeyId });
  },

  runStageJob: async (journeyId: string, stageId: string) => {
    const qs = new URLSearchParams({ stage_id: stageId, triggered_by: "ui" });
    const raw = await apiFetch<unknown>(`/api/v1/journeys/${journeyId}/jobs?${qs.toString()}`, {
      method: "POST",
      body: { stage_id: stageId, triggered_by: "ui" },
    });
    return normalizeStageJob(raw, { journeyId });
  },

  getStageJob: async (journeyId: string, jobId: string) => {
    const raw = await apiFetch<unknown>(`/api/v1/journeys/${journeyId}/jobs/${jobId}`);
    return normalizeStageJob(raw, { journeyId, jobId });
  },

  waitForStageJob: async (
    journeyId: string,
    jobId: string,
    opts?: { intervalMs?: number; timeoutMs?: number },
  ) => {
    const intervalMs = opts?.intervalMs ?? 2_000;
    const timeoutMs = opts?.timeoutMs ?? 600_000;
    const started = Date.now();
    while (Date.now() - started < timeoutMs) {
      const job = await api.getStageJob(journeyId, jobId);
      const status = job.status.toLowerCase();
      if (["completed", "failed", "cancelled"].includes(status)) return job;
      await new Promise((resolve) => setTimeout(resolve, intervalMs));
    }
    throw new Error(`Timed out waiting for job ${jobId}`);
  },

  runAllStageJobs: async (
    journeyId: string,
    _stageIds: string[],
    handlers?: {
      onStageStart?: (stageId: string, job: StageJob) => void;
      onStageComplete?: (stageId: string, job: StageJob) => void;
    },
  ): Promise<StageJob[]> => {
    const job = await api.runJourneyJob(journeyId);
    if (!job.id) throw new Error("Journey job id missing from API response");
    const firstStage = job.stageIds?.[0] ?? job.stageId;
    if (firstStage) handlers?.onStageStart?.(firstStage, job);
    const finished = await api.waitForStageJob(journeyId, job.id);
    if (job.stageIds) {
      for (const stageId of job.stageIds) {
        handlers?.onStageComplete?.(stageId, finished);
      }
    } else if (firstStage) {
      handlers?.onStageComplete?.(firstStage, finished);
    }
    if (["failed", "cancelled"].includes(finished.status.toLowerCase())) {
      throw new Error(`Journey job ended with status ${finished.status}`);
    }
    return [finished];
  },

  cancelStageJob: (journeyId: string, jobId: string) =>
    apiFetch<unknown>(`/api/v1/journeys/${journeyId}/jobs/${jobId}/cancel`, { method: "POST", body: {} }),

  deleteStageJob: (journeyId: string, jobId: string) =>
    apiFetch<{ success: boolean; message?: string }>(`/api/v1/journeys/${journeyId}/jobs/${jobId}`, {
      method: "DELETE",
    }),

  batchDeleteStageJobs: (journeyId: string, jobIds: string[]) =>
    apiFetch<{ success: boolean; message?: string; data?: { successful?: number; total?: number } }>(
      `/api/v1/journeys/${journeyId}/jobs/batch-delete`,
      { method: "POST", body: { job_ids: jobIds } },
    ),

  fetchJobStepLogs: async (
    journeyId: string,
    jobId: string,
    stageId: string,
    stepId: string,
  ): Promise<Array<{ timestamp?: string; level?: string; message?: string; log_message?: string }>> => {
    const raw = await apiFetch<{ data?: { logs?: unknown[] }; logs?: unknown[] }>(
      `/api/v1/journeys/${journeyId}/jobs/${jobId}/logs`,
      { query: { stage_name: stageId, step_name: stepId, limit: 500 } },
    );
    const arr = Array.isArray(raw) ? raw : (raw?.data?.logs ?? raw?.logs ?? []);
    return Array.isArray(arr) ? (arr as Array<{ timestamp?: string; level?: string; message?: string; log_message?: string }>) : [];
  },

  listAllRuns: async (): Promise<UnifiedRunRow[]> => {
    const [journeys, dslExecutions] = await Promise.all([
      api.listSimpleJourneys(),
      api.listExecutions().catch(() => [] as ExecutionSummary[]),
    ]);
    const jobGroups = await Promise.all(
      journeys.map(async (j) => {
        const jobs = await api.listJourneyJobs(j.journeyId).catch(() => [] as StageJob[]);
        return jobs.map(
          (job): UnifiedRunRow => ({
            kind: "stage_job",
            id: job.id,
            journeyId: j.journeyId,
            journeyName: j.name,
            jobType: job.jobType,
            stageIds: job.stageIds,
            stageId: job.jobType === "journey" ? undefined : job.stageId,
            status: job.status,
            startedAt: job.startedAt,
          }),
        );
      }),
    );
    const dslRows: UnifiedRunRow[] = dslExecutions.map((ex) => ({
      kind: "dsl_execution",
      id: ex.execution_id,
      journeyId: ex.journey_id,
      status: ex.status,
    }));
    return [...jobGroups.flat(), ...dslRows].sort((a, b) => {
      const ta = a.kind === "stage_job" ? a.startedAt ?? "" : "";
      const tb = b.kind === "stage_job" ? b.startedAt ?? "" : "";
      return tb.localeCompare(ta);
    });
  },

  exportJourney: (id: string, version?: number) =>
    apiFetch<{ journey_id: string; yaml: string }>(`/api/v1/journeys/${id}/export`, {
      query: version ? { version } : undefined,
    }),

  validateJourneyYaml: (yaml: string, strictTools = false) =>
    apiFetch<ValidationResult>("/api/v1/journeys/validate", {
      method: "POST",
      headers: { "Content-Type": "application/yaml" },
      rawBody: yaml,
      query: { strict_tools: strictTools ? "true" : "false" },
    }),

  validateStoredJourney: (journeyId: string) =>
    apiFetch<ValidationResult>(`/api/v1/journeys/${journeyId}/validate`, { method: "POST" }),

  createDslJourney: (yaml: string) =>
    apiFetch<Record<string, unknown>>("/api/v1/journeys/dsl", {
      method: "POST",
      headers: { "Content-Type": "application/yaml" },
      rawBody: yaml,
    }),

  listTools: (domain?: string) =>
    apiFetch<{ tools: ToolDescriptor[]; total: number }>("/api/v1/tools", {
      query: domain ? { domain } : undefined,
    }),

  listSchedules: (journeyId?: string) =>
    apiFetch<{ success: boolean; data: ScheduleRow[]; total: number }>("/api/v1/schedules/", {
      query: journeyId ? { journey_id: journeyId } : undefined,
    }),

  fleetSummary: () => apiFetch<FleetSummary>("/api/v1/fleet/summary"),

  fleetMetrics: (window = "24h") =>
    apiFetch<FleetMetrics>("/api/v1/fleet/metrics", { query: { window } }),

  fleetWorkers: () => apiFetch<{ workers: FleetWorker[]; generated_at: string }>("/api/v1/fleet/workers"),

  queueSummary: () => apiFetch<QueueSummary>("/api/v1/queue/summary"),

  queueJobs: (state = "all", limit = 50) =>
    apiFetch<QueueJobsResponse>("/api/v1/queue/jobs", { query: { state, limit } }),

  workersSummary: () => apiFetch<WorkersSummary>("/api/v1/workers/summary"),

  listQueueWorkers: () => apiFetch<{ workers: WorkerRow[]; generated_at: string }>("/api/v1/workers"),

  scaleWorkers: (replicas: number) =>
    apiFetch<{ replicas: number; capability: string; deployment?: { desired: number; ready: number; available: number; name: string } }>(
      "/api/v1/workers/scale",
      {
        method: "PATCH",
        body: { replicas },
      },
    ),

  configureWorkerAutoscaling: (body: {
    enabled: boolean;
    min_replicas: number;
    max_replicas: number;
    lag_threshold: number;
  }) =>
    apiFetch<Record<string, unknown>>("/api/v1/workers/autoscaling", {
      method: "PATCH",
      body,
    }),
};

export const fetchVersion = api.version;
