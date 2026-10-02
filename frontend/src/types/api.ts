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

export type SimpleJourneySummary = {
  journeyId: string;
  name: string;
  description?: string;
  status: string;
  odaComponentType?: string;
  overallProgress?: number;
  totalJobs?: number;
  completedJobs?: number;
  runningJobs?: number;
  failedJobs?: number;
  createdAt?: string;
  updatedAt?: string;
};

export type JourneyListResponse = {
  success: boolean;
  total: number;
  data: SimpleJourneySummary[];
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
  scheduleId: string;
  journeyId: string;
  stageId?: string;
  intervalMinutes: number;
  enabled: boolean;
  timezone?: string;
  lastRunAt?: string | null;
  nextRunAt?: string | null;
  lastJobId?: string | null;
  lastJobStatus?: string | null;
  createdAt?: string;
  createdBy?: string;
};

export type ArchivedJobRow = {
  job_id: string;
  journey_id?: string;
  execution_number?: number | string;
  stage_id?: string;
  stage_name?: string;
  status?: string;
  start_time?: string;
  end_time?: string;
  duration?: number | string;
  triggered_by?: string;
};

export type FleetSummary = {
  active: number;
  queued: number;
  failed: number;
  workers: number;
  global_limit: number;
  running_counter?: number | null;
  dsl_executions_active?: number;
  dsl_executions_queued?: number;
  stage_jobs_active?: number;
  stage_jobs_queued?: number;
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

export type QueueJob = {
  stream_id: string;
  job_id: string;
  journey_id: string;
  job_kind: string;
  stage_id?: string;
  state: "waiting" | "claimed" | "running";
  consumer_name?: string;
  idle_ms?: number;
  enqueued_at?: number | null;
  triggered_by?: string;
};

export type QueueSummary = {
  lag: number;
  pending: number;
  active: number;
  queued: number;
  max_global: number;
  consumer_count: number;
  worker_threads?: number;
  running_capacity?: number;
  generated_at: string;
};

export type QueueJobsResponse = {
  jobs: QueueJob[];
  count: number;
  state: string;
};

export type WorkerRow = {
  worker_id: string;
  consumer_name?: string | null;
  status: string;
  pending_jobs: number;
  idle_ms: number;
  current_job?: {
    job_id: string;
    journey_id: string;
    idle_ms?: number;
  } | null;
  phase?: string | null;
  restarts?: number;
  start_time?: string | null;
  last_seen: string;
};

export type EngineSettings = {
  workers: {
    replicas?: number;
    desired?: number;
    ready?: number;
    max_replicas?: number;
    threads: number;
    threads_min: number;
    threads_max: number;
    k8s_available?: boolean;
    autoscaling?: {
      enabled: boolean;
      min_replicas: number;
      max_replicas: number;
      lag_threshold: number;
      horizon_waves?: number;
      threads?: number;
      keda_available?: boolean;
    };
  };
  queue: {
    mode: string;
    redis_available: boolean;
    max_global_jobs: number;
    min_global_jobs: number;
    max_global_jobs_cap: number;
    stream_key: string;
    consumer_group: string;
  };
  scheduler: {
    running: boolean;
    schedule_count: number;
    enabled_count: number;
    check_interval_sec: number;
  };
  version: {
    name: string;
    version: string;
    env: string;
    git_sha?: string;
  };
  notes?: string[];
};

export type WorkersSummary = {
  queue_mode: boolean;
  redis_available: boolean;
  k8s_available: boolean;
  deployment: {
    name: string;
    desired: number;
    ready: number;
    available: number;
  };
  replicas: number;
  consumers: number;
  registered_consumers?: number;
  stale_consumers?: number;
  healthy_consumers: number;
  active_jobs: number;
  autoscaling: {
    enabled: boolean;
    min_replicas: number;
    max_replicas: number;
    lag_threshold: number;
    horizon_waves?: number;
    threads?: number;
    keda_available: boolean;
  };
  max_worker_replicas: number;
  generated_at: string;
};
