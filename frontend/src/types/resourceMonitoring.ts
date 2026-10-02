export type ResourceWindow = "1h" | "24h" | "7d";

export interface ResourceKpi {
  id: string;
  label: string;
  value?: number | null;
  unit?: string;
}

export interface ResourcePoint {
  timestamp: string;
  cpu_pct?: number | null;
  memory_pct?: number | null;
  storage_pct?: number | null;
  network_rx_mbps?: number | null;
  network_tx_mbps?: number | null;
  jobs_running?: number;
}

export interface ResourceSummaryResponse {
  window?: ResourceWindow;
  grain?: string;
  timestamp?: string;
  node?: string | null;
  kpis?: ResourceKpi[];
  points?: ResourcePoint[];
  error?: string;
}
