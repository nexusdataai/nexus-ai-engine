/** REST client for Nexus AI Engine (spec 060, 070). */

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
