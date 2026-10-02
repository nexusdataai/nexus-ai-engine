export type DataStoreWindow = "1h" | "24h" | "7d";

export interface DataStoreKpi {
  id: string;
  label: string;
  value?: number | null;
  unit?: string;
}

export interface DynamoTableRow {
  id: string;
  label: string;
  name?: string | null;
  status?: string;
  item_count?: number | null;
  size_human?: string | null;
  gsi_count?: number;
  billing_mode?: string;
  read_rcu?: number | null;
  write_wcu?: number | null;
  read_latency_ms?: number | null;
  write_latency_ms?: number | null;
  error?: string;
}

export interface DynamoPoint {
  timestamp: string;
  read_rcu?: number | null;
  write_wcu?: number | null;
  read_latency_ms?: number | null;
  write_latency_ms?: number | null;
}

export interface DynamoOverview {
  connected?: boolean;
  ping_ms?: number | null;
  ping_message?: string;
  region?: string;
  window?: DataStoreWindow;
  grain?: string;
  table_total?: number;
  tables_active?: number;
  tables?: DynamoTableRow[];
  metrics_source?: string;
  kpis?: DataStoreKpi[];
  points?: DynamoPoint[];
  timestamp?: string;
  error?: string;
}

export interface AthenaRecentQuery {
  id: string;
  state?: string;
  submitted?: string;
  engine_ms?: number;
  bytes_scanned?: number | null;
  bytes_scanned_human?: string | null;
  kind?: string;
}

export interface AthenaPoint {
  timestamp: string;
  read_queries?: number | null;
  write_queries?: number | null;
  bytes_scanned?: number | null;
  avg_engine_ms?: number | null;
}

export interface AthenaOverview {
  connected?: boolean;
  glue_reachable?: boolean;
  athena_reachable?: boolean;
  ping_ms?: number | null;
  ping_message?: string;
  region?: string;
  window?: DataStoreWindow;
  grain?: string;
  points_scope?: string;
  metrics_source?: string;
  database?: string;
  workgroup?: string;
  archive_bucket?: string | null;
  table?: {
    name?: string;
    database?: string;
    exists?: boolean;
    location?: string | null;
    partition_keys?: string[];
    record_count?: number | null;
    partition_count?: number | null;
    partitions_truncated?: boolean;
    error?: string;
  };
  recent_queries?: AthenaRecentQuery[];
  kpis?: DataStoreKpi[];
  points?: AthenaPoint[];
  timestamp?: string;
  error?: string;
}
