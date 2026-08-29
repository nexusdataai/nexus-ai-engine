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
  ScheduleRow,
  ToolDescriptor,
  ValidationResult,
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
            stageId: job.stageId,
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
};

export const fetchVersion = api.version;
