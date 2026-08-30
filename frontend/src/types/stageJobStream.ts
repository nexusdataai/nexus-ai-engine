export type StepStatus = "pending" | "running" | "completed" | "failed" | "cancelled";

export type StepState = {
  status: StepStatus;
  progress: number;
  current?: number;
  total?: number;
};

export type LogEntry = {
  timestamp: string;
  level: string;
  message: string;
  step_id?: string;
};

export type SseConnectionStatus = "idle" | "connecting" | "connected" | "disconnected";
