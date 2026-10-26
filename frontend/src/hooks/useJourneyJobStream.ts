import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { LogEntry, SseConnectionStatus, StepState, StepStatus } from "@/types/stageJobStream";
import type { StageJourneyStage } from "@/types/stageJourney";

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";

export const STEP_PENDING: StepStatus = "pending";
export const STEP_RUNNING: StepStatus = "running";
export const STEP_COMPLETED: StepStatus = "completed";
export const STEP_FAILED: StepStatus = "failed";

function stepKey(stageId: string, stepId: string): string {
  return `${stageId}:${stepId}`;
}

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

function initStepStates(stages: StageJourneyStage[]): Record<string, StepState> {
  const out: Record<string, StepState> = {};
  for (const stage of stages) {
    for (const step of stage.steps) {
      out[stepKey(stage.id, step.id)] = { status: STEP_PENDING, progress: 0 };
    }
  }
  return out;
}

export function useJourneyJobStream(
  journeyId: string,
  stages: StageJourneyStage[],
  jobId: string | null,
  jobStatus: string | null,
  onComplete?: () => void,
) {
  const [stepStates, setStepStates] = useState<Record<string, StepState>>(() => initStepStates(stages));
  const [stepLogs, setStepLogs] = useState<Record<string, LogEntry[]>>({});
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [levelFilter, setLevelFilter] = useState<Record<string, string>>({});
  const [currentStageId, setCurrentStageId] = useState<string | null>(null);
  const [currentStepId, setCurrentStepId] = useState<string | null>(null);
  const [sseStatus, setSseStatus] = useState<SseConnectionStatus>("idle");

  const esRef = useRef<EventSource | null>(null);
  const reconnectRef = useRef(0);
  const stagesRef = useRef(stages);
  stagesRef.current = stages;
  const stageSignature = useMemo(
    () => stages.map((s) => `${s.id}:${s.steps.map((step) => step.id).join(",")}`).join("|"),
    [stages],
  );

  useEffect(() => {
    setStepStates(initStepStates(stagesRef.current));
    setStepLogs({});
    setExpanded({});
    setCurrentStageId(null);
    setCurrentStepId(null);
  }, [stageSignature]);

  const closeStream = useCallback(() => {
    if (esRef.current) {
      try {
        esRef.current.close();
      } catch {
        /* ignore */
      }
      esRef.current = null;
    }
  }, []);

  const stageSteps = useCallback(
    (stageId: string) => stagesRef.current.find((s) => s.id === stageId)?.steps ?? [],
    [],
  );

  const onStepStatus = useCallback((evt: Record<string, unknown>) => {
    const sid = String(evt.step_id ?? pick(evt, "step_id") ?? "");
    const stageId = String(evt.stage_id ?? pick(evt, "stage_id") ?? currentStageId ?? "");
    if (!sid || !stageId) return;
    const key = stepKey(stageId, sid);
    const status = normalizeStepStatus(pick(evt, "status") ?? evt.status);
    const progress = Number(pick(evt, "progress") ?? 0);

    setStepStates((prev) => {
      const next = { ...prev, [key]: { ...(prev[key] ?? { progress: 0 }), status, progress: progress || prev[key]?.progress || 0 } };
      if (status === STEP_RUNNING) {
        const steps = stageSteps(stageId);
        const idx = steps.findIndex((s) => s.id === sid);
        steps.forEach((s, i) => {
          if (i < idx) {
            const pk = stepKey(stageId, s.id);
            const ps = next[pk]?.status;
            if (ps !== STEP_FAILED && ps !== STEP_COMPLETED) {
              next[pk] = { ...(next[pk] ?? { progress: 0 }), status: STEP_COMPLETED, progress: 100 };
            }
          }
        });
      }
      if (status === STEP_COMPLETED) next[key] = { ...(next[key] ?? { progress: 0 }), status, progress: 100 };
      return next;
    });

    if (status === STEP_RUNNING) {
      setCurrentStageId(stageId);
      setCurrentStepId(sid);
      setExpanded((prev) => ({ ...prev, [key]: true }));
    }
    if (status === STEP_FAILED) setExpanded((prev) => ({ ...prev, [key]: true }));
  }, [currentStageId, stageSteps]);

  const onLog = useCallback((evt: Record<string, unknown>) => {
    const sid = String(evt.step_id ?? pick(evt, "step_id") ?? "__unstepped__");
    const stageId = String(evt.stage_id ?? pick(evt, "stage_id") ?? currentStageId ?? "");
    const key = stageId && sid !== "__unstepped__" ? stepKey(stageId, sid) : sid;
    const entry: LogEntry = {
      timestamp: String(evt.timestamp ?? pick(evt, "timestamp") ?? new Date().toISOString()),
      level: String(pick(evt, "level") ?? evt.level ?? "info"),
      message: String(pick(evt, "message") ?? evt.message ?? ""),
      step_id: sid !== "__unstepped__" ? sid : undefined,
    };
    setStepLogs((prev) => ({ ...prev, [key]: [...(prev[key] ?? []), entry] }));
  }, [currentStageId]);

  const connectStream = useCallback(
    (jid: string) => {
      closeStream();
      setSseStatus("connecting");
      const base = API_BASE || window.location.origin;
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

      es.addEventListener("step_status", parse(onStepStatus));
      es.addEventListener("log", parse(onLog));
      es.addEventListener("job_complete", parse(() => {
        setStepStates((prev) => {
          const next = { ...prev };
          for (const stage of stagesRef.current) {
            for (const step of stage.steps) {
              const pk = stepKey(stage.id, step.id);
              if (next[pk]?.status !== STEP_FAILED) {
                next[pk] = { ...(next[pk] ?? { progress: 0 }), status: STEP_COMPLETED, progress: 100 };
              }
            }
          }
          return next;
        });
        setCurrentStageId(null);
        setCurrentStepId(null);
        closeStream();
        setSseStatus("idle");
        onComplete?.();
      }));

      es.onerror = () => {
        setSseStatus("disconnected");
        closeStream();
        reconnectRef.current += 1;
        const terminal = ["completed", "failed", "cancelled"].includes(String(jobStatus ?? "").toLowerCase());
        if (!terminal && reconnectRef.current <= 5) {
          const delay = Math.min(8000, 500 * 2 ** reconnectRef.current);
          setTimeout(() => connectStream(jid), delay);
        }
      };
    },
    [journeyId, closeStream, onStepStatus, onLog, jobStatus, onComplete],
  );

  useEffect(() => {
    if (!jobId || jobStatus == null) return;
    const terminal = ["completed", "failed", "cancelled"].includes(String(jobStatus).toLowerCase());
    if (!terminal) connectStream(jobId);
    return () => closeStream();
  }, [jobId, jobStatus, connectStream, closeStream]);

  const resetForNewJob = useCallback(() => {
    setStepLogs({});
    setStepStates(initStepStates(stagesRef.current));
    const first = stagesRef.current[0];
    setCurrentStageId(first?.id ?? null);
    setCurrentStepId(first?.steps[0]?.id ?? null);
    if (first?.steps[0]) setExpanded({ [stepKey(first.id, first.steps[0].id)]: true });
  }, []);

  const hydrateStepLogs = useCallback((stageId: string, stepId: string, entries: LogEntry[]) => {
    if (!entries.length) return;
    setStepLogs((prev) => ({ ...prev, [stepKey(stageId, stepId)]: entries }));
  }, []);

  const getStepStatus = useCallback(
    (stageId: string, stepId: string): StepStatus | string =>
      stepStates[stepKey(stageId, stepId)]?.status ?? STEP_PENDING,
    [stepStates],
  );

  const getStepLogs = useCallback(
    (stageId: string, stepId: string) => stepLogs[stepKey(stageId, stepId)] ?? [],
    [stepLogs],
  );

  return {
    stepStates,
    stepLogs,
    expanded,
    levelFilter,
    currentStageId,
    currentStepId,
    sseStatus,
    resetForNewJob,
    hydrateStepLogs,
    getStepStatus,
    getStepLogs,
    connectStream,
    closeStream,
    setLevelFilter,
  };
}
