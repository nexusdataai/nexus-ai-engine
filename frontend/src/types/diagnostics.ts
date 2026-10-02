export type DiagnosticCheckStatus = "pass" | "fail" | "warning" | "skipped";
export type DiagnosticOverallStatus = "healthy" | "degraded" | "unhealthy";
export type InfraCategory = "frontend" | "backend" | "dynamodb" | "s3" | "glue-athena" | "redis";

export interface DiagnosticCheckResult {
  status: DiagnosticCheckStatus;
  latency_ms: number;
  message: string;
  details?: Record<string, unknown>;
  error?: string;
}

export interface InfrastructureDiagnosticsResult {
  status: DiagnosticOverallStatus;
  timestamp: string;
  checks: Record<string, DiagnosticCheckResult>;
}
