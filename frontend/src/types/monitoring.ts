/**
 * Infra monitoring / System SLA types
 */

export type SlaStatus = "healthy" | "warning" | "critical" | "unknown";

export interface SlaSummaryMetric {
  label: string;
  value: string;
  status?: SlaStatus;
}

export interface SlaComponent {
  id: string;
  label: string;
  value?: number | null;
  unit?: string;
  weight?: number;
  score?: number | null;
  status?: SlaStatus;
}

export interface SlaLayer {
  score?: number | null;
  status?: SlaStatus;
  components?: SlaComponent[];
}

export interface SlaPillar {
  score?: number | null;
  status?: SlaStatus;
  headline?: string;
  uptime_pct?: number;
  app_layer?: SlaLayer;
  data_layer?: SlaLayer;
  summary_metrics?: SlaSummaryMetric[];
}

export type SlaPillarId =
  | "performance"
  | "availability"
  | "reliability"
  | "security"
  | "compliance";

export interface SlaSummaryResponse {
  window?: string;
  window_hours?: number;
  timestamp?: string;
  overall_score?: number | null;
  overall_status?: SlaStatus;
  source?: string;
  pillars?: Partial<Record<SlaPillarId, SlaPillar>>;
  error?: string;
}

export interface SlaTimelinePoint {
  timestamp: string;
  overall_score?: number | null;
  overall_status?: SlaStatus;
  pillars?: Partial<Record<SlaPillarId, number | null>>;
}

export interface SlaTimelineResponse {
  hours: number;
  points: SlaTimelinePoint[];
  error?: string;
}

export interface SlaPillarDetail extends SlaPillar {
  pillar: SlaPillarId;
  window_hours?: number;
  timestamp?: string;
  timeline?: Array<{ timestamp: string; score?: number | null; status?: SlaStatus }>;
  error?: string;
}

export const SLA_PILLAR_LABELS: Record<SlaPillarId, string> = {
  performance: "Performance",
  availability: "Availability",
  reliability: "Reliability",
  security: "Security",
  compliance: "Compliance",
};

export const SLA_PILLAR_ORDER: SlaPillarId[] = [
  "performance",
  "availability",
  "reliability",
  "security",
  "compliance",
];
