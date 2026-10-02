export interface StaleJob {
  job_id: string;
  journey_id: string;
  stage_id: string;
  current_step: string;
  age_min: number;
  confidence: string;
  pk: string;
  sk: string;
}

export interface StaleJobsResponse {
  summary: {
    total_stale?: number;
    STALE?: number;
    "LIKELY-STUCK"?: number;
    "UNVERIFIED-LONG"?: number;
    blocked_schedules?: number;
  };
  jobs: StaleJob[];
  blocked_schedules?: Array<{ schedule_id: string; journey_id: string; last_job_id: string }>;
}

export interface CrashContainer {
  name: string;
  restart_count: number;
  last_terminated?: {
    reason?: string;
    exit_code?: number;
    finished_at?: string | null;
    message?: string | null;
  } | null;
  previous_log_tail?: string | null;
}

export interface CrashedPod {
  name: string;
  phase?: string;
  restarts: number;
  node?: string | null;
  started_at?: string | null;
  analysis?: string[];
  containers?: CrashContainer[];
  events?: Array<{ type?: string; reason?: string; message?: string; last_seen?: string | null }>;
}

export interface DlqEntry {
  pk: string;
  sk: string;
  job_id: string;
  journey_id: string;
  stage_id: string;
  error: string;
  context?: string;
  timestamp: string;
  status: "pending_review" | "reprocessed" | "dismissed" | string;
  new_job_id?: string | null;
  reprocessed_at?: string | null;
  dismissed_at?: string | null;
}

export interface DlqListResponse {
  table?: string;
  count: number;
  summary: {
    pending_review?: number;
    reprocessed?: number;
    dismissed?: number;
  };
  items: DlqEntry[];
  imported?: number;
  scanned?: number;
}

export interface CrashAnalyzerResponse {
  namespace?: string;
  available?: boolean;
  message?: string;
  via_operator?: boolean;
  log_tail_lines?: number;
  pods: CrashedPod[];
  count?: number;
}
