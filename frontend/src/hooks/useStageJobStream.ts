import { useCallback, useEffect, useRef, useState } from "react";

import type { LogEntry, SseConnectionStatus, StepState, StepStatus } from "@/types/stageJobStream";
import type { RegisteredStageStep } from "@/types/stageJourney";

import { sseBaseUrl } from "@/utils/sseBaseUrl";

export const STEP_PENDING: StepStatus = "pending";
export const STEP_RUNNING: StepStatus = "running";
export const STEP_COMPLETED: StepStatus = "completed";
export const STEP_FAILED: StepStatus = "failed";

function pick(evt: Record<string, unknown> | null | undefined, key: string): unknown {
  if (!evt) return undefined;
  const nested = evt.data;
  if (nested && typeof nested === "object" && !Array.isArray(nested) && key in nested) {
    return (nested as Record<string, unknown>)[key];
  }
  return evt[key];
}

function normalizeStepStatus(raw: unknown): StepStatus {
  const s = String(raw ?? "pending").toLowerCase();
  if (s === "in_progress" || s === "running") return STEP_RUNNING;
  if (s === "completed" || s === "success" || s === "succeeded") return STEP_COMPLETED;
  if (s === "failed" || s === "error") return STEP_FAILED;
  if (s === "cancelled") return "cancelled";
  return STEP_PENDING;
}

function initStepStates(steps: RegisteredStageStep[]): Record<string, StepState> {
  const out: Record<string, StepState> = {};
  for (const s of steps) out[s.id] = { status: STEP_PENDING, progress: 0 };
  return out;
}

export function useStageJobStream(
  journeyId: string,
  steps: RegisteredStageStep[],
  jobId: string | null,
  jobStatus: string | null,
  onComplete?: () => void,
) {
  const [stepStates, setStepStates] = useState<Record<string, StepState>>(() => initStepStates(steps));
  const [stepLogs, setStepLogs] = useState<Record<string, LogEntry[]>>({});
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [levelFilter, setLevelFilter] = useState<Record<string, string>>({});
  const [currentStepId, setCurrentStepId] = useState<string | null>(null);
  const [sseStatus, setSseStatus] = useState<SseConnectionStatus>("idle");

  const esRef = useRef<EventSource | null>(null);
  const reconnectRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const autoCollapseRef = useRef(true);
  const stepsRef = useRef(steps);
  stepsRef.current = steps;
  const jobStatusRef = useRef(jobStatus);
  jobStatusRef.current = jobStatus;
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  useEffect(() => {
    setStepStates(initStepStates(steps));
    setStepLogs({});
    setExpanded({});
    setCurrentStepId(steps[0]?.id ?? null);
  }, [steps]);

  const closeStream = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (esRef.current) {
      try {
        esRef.current.close();
      } catch {
        /* ignore */
      }
      esRef.current = null;
    }
  }, []);

  const handleStepStatus = useCallback((evt: Record<string, unknown>) => {
    const sid = String(evt.step_id ?? pick(evt, "step_id") ?? "");
    if (!sid) return;
    const status = normalizeStepStatus(pick(evt, "status") ?? evt.status);
    const progress = Number(pick(evt, "progress") ?? 0);

    setStepStates((prev) => {
      const next = { ...prev, [sid]: { ...(prev[sid] ?? { progress: 0 }), status, progress: progress || prev[sid]?.progress || 0 } };
      if (status === STEP_RUNNING) {
        const stageSteps = stepsRef.current;
        const idx = stageSteps.findIndex((s) => s.id === sid);
        stageSteps.forEach((s, i) => {
          if (i < idx) {
            const ps = next[s.id]?.status;
            if (ps !== STEP_FAILED && ps !== STEP_COMPLETED) {
              next[s.id] = { ...(next[s.id] ?? { progress: 0 }), status: STEP_COMPLETED, progress: 100 };
            }
          }
        });
      }
      if (status === STEP_COMPLETED) next[sid] = { ...(next[sid] ?? { progress: 0 }), status, progress: 100 };
      return next;
    });

    if (status === STEP_RUNNING) {
      setCurrentStepId(sid);
      setExpanded((prev) => (autoCollapseRef.current ? { [sid]: true } : { ...prev, [sid]: true }));
    }
    if (status === STEP_FAILED) setExpanded((prev) => ({ ...prev, [sid]: true }));
  }, []);

  const handleLog = useCallback((evt: Record<string, unknown>) => {
    const sid = String(evt.step_id ?? pick(evt, "step_id") ?? "__unstepped__");
    const entry: LogEntry = {
      timestamp: String(evt.timestamp ?? pick(evt, "timestamp") ?? new Date().toISOString()),
      level: String(pick(evt, "level") ?? evt.level ?? "info"),
      message: String(pick(evt, "message") ?? evt.message ?? ""),
      step_id: sid !== "__unstepped__" ? sid : undefined,
    };
    setStepLogs((prev) => ({ ...prev, [sid]: [...(prev[sid] ?? []), entry] }));
  }, []);

  const handleTaskProgress = useCallback((evt: Record<string, unknown>) => {
    const sid = String(evt.step_id ?? pick(evt, "step_id") ?? "");
    if (!sid) return;
    const progress = Number(pick(evt, "progress") ?? pick(evt, "percentage") ?? 0);
    const current = pick(evt, "current");
    const total = pick(evt, "total");
    setStepStates((prev) => ({
      ...prev,
      [sid]: {
        ...(prev[sid] ?? { progress: 0, status: STEP_PENDING }),
        status: prev[sid]?.status === STEP_COMPLETED ? STEP_COMPLETED : STEP_RUNNING,
        progress: progress || prev[sid]?.progress || 0,
        ...(current != null ? { current: Number(current) } : {}),
        ...(total != null ? { total: Number(total) } : {}),
      },
    }));
  }, []);

  const handleJobComplete = useCallback(() => {
    setStepStates((prev) => {
      const next = { ...prev };
      for (const s of stepsRef.current) {
        if (next[s.id]?.status !== STEP_FAILED) {
          next[s.id] = { ...(next[s.id] ?? { progress: 0 }), status: STEP_COMPLETED, progress: 100 };
        }
      }
      return next;
    });
    setCurrentStepId(null);
    closeStream();
    setSseStatus("idle");
    onCompleteRef.current?.();
  }, [closeStream]);

  const connectStream = useCallback(
    (jid: string) => {
      closeStream();
      setSseStatus("connecting");
      const base = sseBaseUrl();
      const es = new EventSource(`${base}/api/v1/journeys/${journeyId}/jobs/${jid}/stream`);
      esRef.current = es;

      const markConnected = () => {
        reconnectRef.current = 0;
        setSseStatus("connected");
      };

      es.onopen = () => markConnected();

      const parse = (handler: (data: Record<string, unknown>) => void) => (e: MessageEvent) => {
        try {
          markConnected();
          handler(JSON.parse(e.data) as Record<string, unknown>);
        } catch {
          /* ignore */
        }
      };

      es.addEventListener("step_status", parse(handleStepStatus));
      es.addEventListener("log", parse(handleLog));
      es.addEventListener("task_progress", parse(handleTaskProgress));
      es.addEventListener("job_complete", parse(() => handleJobComplete()));

      es.onerror = () => {
        setSseStatus("disconnected");
        closeStream();
        reconnectRef.current += 1;
        const terminal = ["completed", "failed", "cancelled"].includes(
          String(jobStatusRef.current ?? "").toLowerCase(),
        );
        if (!terminal && reconnectRef.current <= 8) {
          const delay = Math.min(8000, 500 * 2 ** reconnectRef.current);
          reconnectTimerRef.current = setTimeout(() => connectStream(jid), delay);
        }
      };
    },
    [journeyId, closeStream, handleStepStatus, handleLog, handleTaskProgress, handleJobComplete],
  );

  const connectStreamRef = useRef(connectStream);
  connectStreamRef.current = connectStream;

  useEffect(() => {
    if (!jobId) return;
    const terminal = ["completed", "failed", "cancelled"].includes(String(jobStatus ?? "").toLowerCase());
    if (!terminal) connectStreamRef.current(jobId);
    return () => closeStream();
  }, [jobId, jobStatus, closeStream]);

  const resetForNewJob = useCallback(() => {
    autoCollapseRef.current = true;
    setStepLogs({});
    setStepStates(initStepStates(stepsRef.current));
    const first = stepsRef.current[0]?.id;
    setExpanded(first ? { [first]: true } : {});
    setCurrentStepId(first ?? null);
  }, []);

  const expandAll = useCallback(() => {
    autoCollapseRef.current = false;
    const next: Record<string, boolean> = {};
    for (const s of stepsRef.current) next[s.id] = true;
    setExpanded(next);
  }, []);

  const collapseAll = useCallback(() => {
    autoCollapseRef.current = true;
    setExpanded({});
  }, []);

  const toggleExpanded = useCallback((stepId: string) => {
    setExpanded((prev) => ({ ...prev, [stepId]: !prev[stepId] }));
  }, []);

  const setStepLevelFilter = useCallback((stepId: string, level: string) => {
    setLevelFilter((prev) => ({ ...prev, [stepId]: level }));
  }, []);

  const hydrateStepLogs = useCallback((stepId: string, entries: LogEntry[]) => {
    if (!entries.length) return;
    setStepLogs((prev) => ({ ...prev, [stepId]: entries }));
  }, []);

  return {
    stepStates,
    stepLogs,
    expanded,
    levelFilter,
    currentStepId,
    sseStatus,
    resetForNewJob,
    expandAll,
    collapseAll,
    toggleExpanded,
    setStepLevelFilter,
    hydrateStepLogs,
    connectStream,
    closeStream,
  };
}
