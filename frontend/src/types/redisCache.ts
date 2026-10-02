export interface RedisSnapshotKey {
  id: string;
  key: string;
  label: string;
  length: number;
}

export interface RedisCacheOverview {
  connected?: boolean;
  ping_ms?: number | null;
  ping_message?: string;
  memory?: {
    used_memory_human?: string;
    maxmemory_human?: string;
  };
  effective_config?: {
    redis_host?: string;
    job_stream_key?: string;
    consumer_group?: string;
    queue_mode?: boolean;
    sse_history_max?: number;
  };
  snapshots?: {
    keys?: RedisSnapshotKey[];
    key_total?: number;
  };
  queue?: {
    stream_length?: number;
    waiting?: number;
    active?: number;
    pending?: number;
    consumers?: number;
    cancelled?: number;
    protected?: boolean;
  };
  sse?: {
    key_total?: number;
    keys?: string[];
    match?: string;
  };
  timestamp?: string;
  error?: string;
}

export interface RedisFlushResponse {
  flushed?: boolean;
  collected?: boolean;
  keys_deleted?: number;
  keys?: string[];
  error?: string;
}
