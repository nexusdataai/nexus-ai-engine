export type ExecutionSummary = {
  execution_id: string;
  journey_id: string;
  status: string;
  revision?: number;
  tenant_id?: string;
};

export type ExecutionNodeState = {
  node_id: string;
  status: string;
  display_name?: string;
  started_at?: string | null;
  finished_at?: string | null;
};

export type ExecutionGraph = {
  id: string;
  nodes: Array<{
    node_id: string;
    kind: string;
    display_name?: string;
    tool_id?: string | null;
    capability?: string | null;
    depends_on?: string[];
  }>;
  edges: Array<{ from_node: string; to_node: string }>;
};

export type DslJourneySummary = {
  id: string;
  version: number;
  display_name: string;
  labels?: Record<string, string>;
};

export type ValidationResult = {
  valid: boolean;
  errors: Array<{ path: string; message: string }>;
  warnings: Array<{ path: string; message: string }>;
};

export type ToolDescriptor = {
  id: string;
  version: string;
  display_name: string;
  domain: string;
  description?: string;
  capabilities?: Array<{ name: string; display_name: string; description?: string }>;
};

export type ScheduleRow = {
  schedule_id: string;
  journey_id: string;
  stage_id: string;
  interval_minutes: number;
  enabled: boolean;
  timezone?: string;
};

export type FleetSummary = {
  active: number;
  queued: number;
  failed: number;
  workers: number;
  global_limit: number;
  running_counter?: number | null;
  generated_at: string;
};

export type FleetMetrics = {
  window_hours: number;
  throughput: { submitted: number; succeeded: number; failed: number };
  tool_dispatch_p95_ms: number | null;
  timeline: Array<{ hour: string; succeeded: number; failed: number }>;
  generated_at: string;
};

export type FleetWorker = {
  worker_id: string;
  role: string;
  status: string;
  active_tasks?: number;
  execution_id?: string | null;
  lock_expires_at?: string | null;
  last_seen: string;
};
