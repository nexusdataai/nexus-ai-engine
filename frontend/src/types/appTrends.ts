export type AppTrendsTab = "executions" | "queue" | "schedules";
export type AppTrendsWindow = "24h" | "7d" | "30d";

export interface AppTrendKpi {
  id: string;
  label: string;
  value?: number | null;
  unit?: string;
}

export interface AppTrendSeries {
  id: string;
  label: string;
  color: string;
  axis: "count" | "percent";
}

export interface AppTrendMix {
  id: string;
  label: string;
  value: number;
  color: string;
}

export interface AppTrendPoint {
  timestamp: string;
  succeeded?: number;
  failed?: number;
  submitted?: number;
  waiting?: number;
  running?: number;
  pending?: number;
  rate?: number | null;
}

export interface AppTrendsResponse {
  tab: AppTrendsTab;
  window: AppTrendsWindow;
  grain?: "hour" | "day";
  timestamp?: string;
  kpis?: AppTrendKpi[];
  series?: AppTrendSeries[];
  mix?: AppTrendMix[];
  points?: AppTrendPoint[];
  chart_title?: string;
  error?: string;
}
