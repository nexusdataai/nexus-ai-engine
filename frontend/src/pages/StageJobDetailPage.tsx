import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { StepConsole } from "@/components/stage/StepConsole";
import { WorkflowTree, type SelectedStep } from "@/components/stage/WorkflowTree";
import { EmptyState } from "@/components/EmptyState";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { STEP_PENDING, useJourneyJobStream } from "@/hooks/useJourneyJobStream";
import { cn } from "@/lib/utils";
import { api } from "@/services/api";
import type { LogEntry, StepStatus } from "@/types/stageJobStream";

function stepKey(stageId: string, stepId: string): string {
  return `${stageId}:${stepId}`;
}

export function StageJobDetailPage() {
  const { journeyId = "", jobId = "" } = useParams();
  const [selectedStep, setSelectedStep] = useState<SelectedStep | null>(null);
  const [expandedStages, setExpandedStages] = useState<Record<string, boolean>>({});
  const [historicalLogs, setHistoricalLogs] = useState<Record<string, LogEntry[]>>({});
  const userPickedStep = useRef(false);

  const journeyQuery = useQuery({
    queryKey: ["stage-journey", journeyId],
    queryFn: () => api.getStageJourney(journeyId),
    enabled: Boolean(journeyId),
    refetchInterval: 3_000,
  });

  const jobQuery = useQuery({
    queryKey: ["stage-job", journeyId, jobId],
    queryFn: () => api.getStageJob(journeyId, jobId),
    enabled: Boolean(journeyId && jobId),
    refetchInterval: 3_000,
  });

  const job = jobQuery.data;
  const journey = journeyQuery.data;

  const stages = useMemo(() => {
    if (!journey) return [];
    const listJob = journey.jobs.find((j) => j.id === jobId);
    const jobType = job?.jobType ?? listJob?.jobType ?? "stage";
    const stageIds = job?.stageIds?.length ? job.stageIds : listJob?.stageIds;
    if (jobType === "journey" && stageIds?.length) {
      return journey.stages.filter((s) => stageIds.includes(s.id));
    }
    const stage = journey.stages.find((s) => s.id === job?.stageId);
    return stage ? [stage] : [];
  }, [journey, job, jobId]);

  const stream = useJourneyJobStream(journeyId, stages, jobId, job?.status ?? null, () => {
    jobQuery.refetch();
    journeyQuery.refetch();
  });

  const terminal = ["completed", "failed", "cancelled"].includes(String(job?.status ?? "").toLowerCase());

  useEffect(() => {
    if (stages.length === 0) return;
    setExpandedStages(Object.fromEntries(stages.map((s) => [s.id, true])));
  }, [stages]);

  useEffect(() => {
    userPickedStep.current = false;
    setHistoricalLogs({});
    setSelectedStep(null);
  }, [jobId]);

  useEffect(() => {
    if (stages.length === 0) return;
    setSelectedStep((prev) => {
      if (prev) return prev;
      const first = stages[0];
      return first?.steps[0] ? { stageId: first.id, stepId: first.steps[0].id } : null;
    });
  }, [stages]);

  useEffect(() => {
    if (terminal || userPickedStep.current) return;
    if (stream.currentStepId && stream.currentStageId) {
      setSelectedStep({ stageId: stream.currentStageId, stepId: stream.currentStepId });
    }
  }, [stream.currentStepId, stream.currentStageId, terminal]);

  const loadHistoricalStepLogs = useCallback(
    async (stageId: string, stepId: string, force = false) => {
      const key = stepKey(stageId, stepId);
      if (!force && historicalLogs[key]?.length) return;
      try {
        const rows = await api.fetchJobStepLogs(journeyId, jobId, stageId, stepId);
        if (rows.length === 0) return;
        const entries = rows.map((row) => ({
          timestamp: row.timestamp ?? new Date().toISOString(),
          level: row.level ?? "info",
          message: row.message ?? row.log_message ?? "",
          step_id: stepId,
        }));
        setHistoricalLogs((prev) => ({ ...prev, [key]: entries }));
        stream.hydrateStepLogs(stageId, stepId, entries);
      } catch {
        /* non-fatal */
      }
    },
    [historicalLogs, journeyId, jobId, stream.hydrateStepLogs],
  );

  useEffect(() => {
    if (!selectedStep || terminal) return;
    void loadHistoricalStepLogs(selectedStep.stageId, selectedStep.stepId, true);
    const timer = window.setInterval(() => {
      void loadHistoricalStepLogs(selectedStep.stageId, selectedStep.stepId, true);
    }, 2_000);
    return () => window.clearInterval(timer);
  }, [selectedStep, terminal, loadHistoricalStepLogs]);

  useEffect(() => {
    if (!job || !terminal || stages.length === 0) return;
    let cancelled = false;
    (async () => {
      for (const stage of stages) {
        for (const step of stage.steps) {
          try {
            const rows = await api.fetchJobStepLogs(journeyId, jobId, stage.id, step.id);
            if (cancelled || rows.length === 0) continue;
            const entries = rows.map((row) => ({
              timestamp: row.timestamp ?? new Date().toISOString(),
              level: row.level ?? "info",
              message: row.message ?? row.log_message ?? "",
              step_id: step.id,
            }));
            stream.hydrateStepLogs(stage.id, step.id, entries);
            setHistoricalLogs((prev) => ({ ...prev, [stepKey(stage.id, step.id)]: entries }));
          } catch {
            /* non-fatal */
          }
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [job, terminal, stages, journeyId, jobId, stream.hydrateStepLogs]);

  const listJob = journey?.jobs.find((j) => j.id === jobId);
  const resolvedJobType = job?.jobType ?? listJob?.jobType ?? "stage";

  const stageStatus = useCallback(
    (stageId: string) => {
      if (!job) return "pending";
      if (resolvedJobType !== "journey") return job.status;
      const current = stream.currentStageId ?? job.currentStageId ?? job.stageId;
      const ordered = [...stages].sort((a, b) => a.order - b.order);
      const currentIdx = ordered.findIndex((s) => s.id === current);
      const stageIdx = ordered.findIndex((s) => s.id === stageId);
      if (job.status === "completed") return "completed";
      if (stageIdx >= 0 && currentIdx >= 0) {
        if (stageIdx < currentIdx) return "completed";
        if (stageIdx === currentIdx) return job.status;
      }
      return "pending";
    },
    [job, stages, stream.currentStageId, resolvedJobType],
  );

  const stepStatusFn = useCallback(
    (stageId: string, stepId: string) => stream.getStepStatus(stageId, stepId),
    [stream],
  );

  const logCountFn = useCallback(
    (stageId: string, stepId: string) => stream.getStepLogs(stageId, stepId).length,
    [stream],
  );

  const selectedStepMeta = useMemo(() => {
    if (!selectedStep) return null;
    const stage = stages.find((s) => s.id === selectedStep.stageId);
    const step = stage?.steps.find((s) => s.id === selectedStep.stepId);
    if (!stage || !step) return null;
    return { stage, step };
  }, [selectedStep, stages]);

  const selectedLogs = useMemo(() => {
    if (!selectedStep) return [];
    const live = stream.getStepLogs(selectedStep.stageId, selectedStep.stepId);
    if (live.length) return live;
    return historicalLogs[stepKey(selectedStep.stageId, selectedStep.stepId)] ?? [];
  }, [selectedStep, stream, historicalLogs]);
  const selectedStepStatus: StepStatus = selectedStep
    ? (stream.getStepStatus(selectedStep.stageId, selectedStep.stepId) as StepStatus)
    : STEP_PENDING;

  const resolvedStageIds = job?.stageIds?.length ? job.stageIds : listJob?.stageIds;
  const scopeLabel =
    resolvedJobType === "journey"
      ? `Journey run (${resolvedStageIds?.length ?? stages.length} stages)`
      : (job?.stageName ?? job?.stageId ?? "Stage job");

  return (
    <div className="space-y-4">
      <Button variant="ghost" size="sm" asChild className="-ml-2">
        <Link to={`/journeys/${journeyId}`}>
          <ArrowLeft className="h-4 w-4" />
          Back to journey
        </Link>
      </Button>

      {jobQuery.isLoading ? (
        <p className="text-sm text-muted-foreground">Loading job…</p>
      ) : jobQuery.error || !job ? (
        <EmptyState title="Job not found" description={String(jobQuery.error ?? "Unknown job")} />
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-xl font-semibold font-mono">{job.id}</h2>
              <p className="text-sm text-muted-foreground">
                {scopeLabel} · {journey?.name ?? journeyId}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <StatusBadge status={job.status} />
              <span
                className={cn(
                  "text-xs px-2 py-0.5 rounded-full border",
                  stream.sseStatus === "connected" && "border-emerald-500/50 text-emerald-400",
                  stream.sseStatus === "connecting" && "border-amber-500/50 text-amber-400",
                  stream.sseStatus === "idle" && terminal && "border-border text-muted-foreground",
                )}
                data-testid="sse-status"
              >
                SSE: {terminal ? "finished" : stream.sseStatus}
              </span>
            </div>
          </div>

          <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
            <span>{Math.round(job.progress)}% progress</span>
            <span>Started {job.startedAt ?? "—"}</span>
            <span>Duration {job.duration ?? "—"}</span>
          </div>

          {stages.length === 0 ? (
            <EmptyState title="No stages" description="No stage metadata found for this job." />
          ) : (
            <div className="grid gap-4 lg:grid-cols-[minmax(260px,340px)_1fr] lg:items-start">
              <WorkflowTree
                stages={stages}
                stageStatus={stageStatus}
                stepStatus={stepStatusFn}
                logCount={logCountFn}
                expandedStages={expandedStages}
                selectedStep={selectedStep}
                onToggleStage={(stageId) =>
                  setExpandedStages((prev) => ({ ...prev, [stageId]: !prev[stageId] }))
                }
                onSelectStep={(stageId, stepId) => {
                  userPickedStep.current = true;
                  setSelectedStep({ stageId, stepId });
                  void loadHistoricalStepLogs(stageId, stepId);
                }}
              />

              <div className="rounded-md border border-border bg-card overflow-hidden min-h-[420px] flex flex-col">
                {selectedStepMeta ? (
                  <>
                    <div className="px-4 py-3 border-b border-border bg-muted/20">
                      <p className="text-sm font-medium">{selectedStepMeta.step.name}</p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {selectedStepMeta.stage.name}
                        {selectedStepMeta.step.description ? ` · ${selectedStepMeta.step.description}` : ""}
                      </p>
                    </div>
                    <div className="flex-1 p-3 min-h-0">
                      <StepConsole
                        key={stepKey(selectedStepMeta.stage.id, selectedStepMeta.step.id)}
                        stepId={selectedStepMeta.step.id}
                        stepName={selectedStepMeta.step.name}
                        status={selectedStepStatus}
                        logs={selectedLogs}
                        levelFilter={
                          selectedStep
                            ? stream.levelFilter[stepKey(selectedStep.stageId, selectedStep.stepId)] ?? "all"
                            : "all"
                        }
                        onLevelFilterChange={(lv) => {
                          if (!selectedStep) return;
                          stream.setLevelFilter((prev) => ({
                            ...prev,
                            [stepKey(selectedStep.stageId, selectedStep.stepId)]: lv,
                          }));
                        }}
                        variant="panel"
                      />
                    </div>
                  </>
                ) : (
                  <div className="flex flex-1 items-center justify-center p-8 text-sm text-muted-foreground">
                    Select a step to view logs
                  </div>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
