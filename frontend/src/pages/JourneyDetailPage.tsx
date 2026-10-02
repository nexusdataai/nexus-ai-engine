import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Play, RefreshCw, Square } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ArchivedJobsSearch } from "@/components/schedules/ArchivedJobsSearch";
import { BatchSchedulesPanel } from "@/components/schedules/BatchSchedulesPanel";
import { StepConsole } from "@/components/stage/StepConsole";
import { WorkflowTree, type SelectedStep } from "@/components/stage/WorkflowTree";
import { EmptyState } from "@/components/EmptyState";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { STEP_PENDING, useJourneyJobStream } from "@/hooks/useJourneyJobStream";
import { cn } from "@/lib/utils";
import { api } from "@/services/api";
import type { LogEntry, StepStatus } from "@/types/stageJobStream";
import type { StageJob } from "@/types/stageJourney";

function stepKey(stageId: string, stepId: string): string {
  return `${stageId}:${stepId}`;
}

function normalizeRunStatus(status: string): StepStatus | string {
  const s = status.toLowerCase();
  if (s === "running" || s === "in_progress" || s === "queued") return "running";
  if (s === "completed" || s === "success" || s === "succeeded") return "completed";
  if (s === "failed" || s === "error") return "failed";
  if (s === "cancelled") return "cancelled";
  return "pending";
}

function jobCoversStage(job: StageJob, stageId: string): boolean {
  if (job.jobType === "journey") {
    return job.stageIds?.includes(stageId) ?? true;
  }
  return job.stageId === stageId;
}

function jobStageLabel(job: StageJob): string {
  if (job.jobType === "journey") {
    const count = job.stageIds?.length ?? 0;
    return count > 0 ? `All stages (${count})` : "Journey run";
  }
  return job.stageName ?? job.stageId;
}

export function JourneyDetailPage() {
  const { journeyId = "" } = useParams();
  const qc = useQueryClient();

  const journeyQuery = useQuery({
    queryKey: ["stage-journey", journeyId],
    queryFn: () => api.getStageJourney(journeyId),
    enabled: Boolean(journeyId),
    refetchInterval: 5_000,
  });

  const journey = journeyQuery.data;
  const orderedStages = useMemo(
    () => (journey ? [...journey.stages].sort((a, b) => a.order - b.order) : []),
    [journey],
  );

  const [selectedStageId, setSelectedStageId] = useState<string | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<string | null>(null);
  const [pipelineError, setPipelineError] = useState<string | null>(null);
  const [isPipelineRunning, setIsPipelineRunning] = useState(false);
  const [expandedStages, setExpandedStages] = useState<Record<string, boolean>>({});
  const [selectedStep, setSelectedStep] = useState<SelectedStep | null>(null);
  const [historicalLogs, setHistoricalLogs] = useState<Record<string, LogEntry[]>>({});

  const streamRef = useRef<ReturnType<typeof useJourneyJobStream> | null>(null);

  useEffect(() => {
    if (orderedStages.length && !selectedStageId) {
      setSelectedStageId(orderedStages[0].id);
      setExpandedStages({ [orderedStages[0].id]: true });
    }
  }, [orderedStages, selectedStageId]);

  const onJobComplete = useCallback(() => {
    qc.invalidateQueries({ queryKey: ["stage-journey", journeyId] });
    qc.invalidateQueries({ queryKey: ["runs"] });
  }, [qc, journeyId]);

  const stream = useJourneyJobStream(journeyId, orderedStages, activeJobId, jobStatus, onJobComplete);
  streamRef.current = stream;

  const activeJob = useMemo(
    () => journey?.jobs.find((j) => j.id === activeJobId) ?? null,
    [journey, activeJobId],
  );

  const beginJourneyJob = useCallback((job: StageJob) => {
    const firstStage = job.currentStageId ?? job.stageIds?.[0] ?? job.stageId;
    if (firstStage) {
      setSelectedStageId(firstStage);
      setExpandedStages((prev) => ({ ...prev, [firstStage]: true }));
    }
    setActiveJobId(job.id);
    setJobStatus(job.status);
    streamRef.current?.resetForNewJob();
    streamRef.current?.connectStream(job.id);
  }, []);

  useEffect(() => {
    if (!journey || activeJobId) return;
    const running = journey.jobs.find((j) =>
      ["running", "in_progress", "queued"].includes(j.status.toLowerCase()),
    );
    if (running) beginJourneyJob(running);
  }, [journey, activeJobId, beginJourneyJob]);

  useEffect(() => {
    if (!activeJobId || !journey) return;
    const job = journey.jobs.find((j) => j.id === activeJobId);
    if (job) setJobStatus(job.status);
  }, [journey, activeJobId]);

  const jobIsLive = Boolean(
    activeJob && !["completed", "failed", "cancelled"].includes(activeJob.status.toLowerCase()),
  );

  useEffect(() => {
    if (!jobIsLive || !stream.currentStepId || !stream.currentStageId) return;
    setSelectedStep({ stageId: stream.currentStageId, stepId: stream.currentStepId });
    setSelectedStageId(stream.currentStageId);
  }, [stream.currentStepId, stream.currentStageId, jobIsLive]);

  useEffect(() => {
    if (!activeJobId || !journey) return;
    const job = journey.jobs.find((j) => j.id === activeJobId);
    if (!job) return;
    const terminal = ["completed", "failed", "cancelled"].includes(job.status.toLowerCase());

    let cancelled = false;
    (async () => {
      for (const stage of orderedStages) {
        if (job.jobType === "journey" && job.stageIds && !job.stageIds.includes(stage.id)) continue;
        if (job.jobType !== "journey" && job.stageId !== stage.id) continue;
        for (const step of stage.steps) {
          try {
            const rows = await api.fetchJobStepLogs(journeyId, activeJobId, stage.id, step.id);
            if (cancelled || rows.length === 0) continue;
            const entries = rows.map((row) => ({
              timestamp: row.timestamp ?? new Date().toISOString(),
              level: row.level ?? "info",
              message: row.message ?? row.log_message ?? "",
              step_id: step.id,
            }));
            if (terminal) {
              stream.hydrateStepLogs(stage.id, step.id, entries);
              setHistoricalLogs((prev) => ({ ...prev, [stepKey(stage.id, step.id)]: entries }));
            }
          } catch {
            /* non-fatal */
          }
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activeJobId, journey, journeyId, orderedStages, stream.hydrateStepLogs]);

  const latestJobForStage = useCallback(
    (stageId: string) => {
      if (!journey) return undefined;
      return journey.jobs.find((j) => jobCoversStage(j, stageId));
    },
    [journey],
  );

  const loadHistoricalStepLogs = useCallback(
    async (stageId: string, stepId: string) => {
      const key = stepKey(stageId, stepId);
      if (historicalLogs[key]?.length) return;
      const job = latestJobForStage(stageId);
      if (!job) return;
      try {
        const rows = await api.fetchJobStepLogs(journeyId, job.id, stageId, stepId);
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
    [historicalLogs, journeyId, latestJobForStage, stream.hydrateStepLogs],
  );

  const stageStatus = useCallback(
    (stageId: string): StepStatus | string => {
      if (activeJobId && activeJob?.jobType === "journey") {
        const current = stream.currentStageId ?? activeJob.currentStageId ?? activeJob.stageId;
        const currentIdx = orderedStages.findIndex((s) => s.id === current);
        const stageIdx = orderedStages.findIndex((s) => s.id === stageId);
        if (["completed"].includes(String(jobStatus ?? "").toLowerCase())) return "completed";
        if (stageIdx >= 0 && currentIdx >= 0) {
          if (stageIdx < currentIdx) return "completed";
          if (stageIdx === currentIdx) return normalizeRunStatus(jobStatus ?? "running");
        }
        return "pending";
      }
      const job = latestJobForStage(stageId);
      if (job && job.id === activeJobId) return normalizeRunStatus(jobStatus ?? job.status);
      return job ? normalizeRunStatus(job.status) : "pending";
    },
    [activeJob, activeJobId, jobStatus, latestJobForStage, orderedStages, stream.currentStageId],
  );

  const stepStatusFn = useCallback(
    (stageId: string, stepId: string): StepStatus | string => {
      if (activeJobId) {
        const live = stream.getStepStatus(stageId, stepId);
        if (live !== STEP_PENDING) return live;
      }
      const job = latestJobForStage(stageId);
      if (job && ["completed", "success"].includes(job.status.toLowerCase())) return "completed";
      if (job && ["failed", "error"].includes(job.status.toLowerCase())) return "failed";
      return STEP_PENDING;
    },
    [activeJobId, latestJobForStage, stream],
  );

  const logCount = useCallback(
    (stageId: string, stepId: string) => {
      const live = stream.getStepLogs(stageId, stepId).length;
      if (live > 0) return live;
      return (historicalLogs[stepKey(stageId, stepId)] ?? []).length;
    },
    [stream, historicalLogs],
  );

  const watchJob = useCallback(
    (job: StageJob) => {
      beginJourneyJob(job);
    },
    [beginJourneyJob],
  );

  const startPipeline = useCallback(async () => {
    if (!journey?.stages.length || isPipelineRunning) return;

    setIsPipelineRunning(true);
    setPipelineError(null);
    setExpandedStages(Object.fromEntries(orderedStages.map((s) => [s.id, true])));

    try {
      const job = await api.runJourneyJob(journeyId);
      beginJourneyJob(job);
      const finished = await api.waitForStageJob(journeyId, job.id);
      setJobStatus(finished.status);
      qc.invalidateQueries({ queryKey: ["stage-journey", journeyId] });
      qc.invalidateQueries({ queryKey: ["runs"] });
    } catch (err) {
      setPipelineError(String(err));
    } finally {
      setIsPipelineRunning(false);
      qc.invalidateQueries({ queryKey: ["stage-journey", journeyId] });
      qc.invalidateQueries({ queryKey: ["runs"] });
    }
  }, [beginJourneyJob, isPipelineRunning, journey, journeyId, orderedStages, qc]);

  const cancelMut = useMutation({
    mutationFn: () => api.cancelStageJob(journeyId, activeJobId!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["stage-journey", journeyId] });
    },
  });

  const isRunning = useMemo(
    () =>
      isPipelineRunning ||
      ["running", "in_progress", "queued"].includes(String(jobStatus ?? "").toLowerCase()),
    [jobStatus, isPipelineRunning],
  );

  const selectedStepMeta = useMemo(() => {
    if (!selectedStep || !journey) return null;
    const stage = journey.stages.find((s) => s.id === selectedStep.stageId);
    const step = stage?.steps.find((s) => s.id === selectedStep.stepId);
    if (!stage || !step) return null;
    return { stage, step };
  }, [selectedStep, journey]);

  const selectedLogs = useMemo(() => {
    if (!selectedStep) return [];
    const live = stream.getStepLogs(selectedStep.stageId, selectedStep.stepId);
    if (live.length) return live;
    return historicalLogs[stepKey(selectedStep.stageId, selectedStep.stepId)] ?? [];
  }, [selectedStep, stream, historicalLogs]);

  const selectedStepStatus = useMemo(() => {
    if (!selectedStep) return STEP_PENDING;
    const s = stepStatusFn(selectedStep.stageId, selectedStep.stepId);
    return typeof s === "string" ? (s as StepStatus) : STEP_PENDING;
  }, [selectedStep, stepStatusFn]);

  if (journeyQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">Loading journey…</p>;
  }
  if (journeyQuery.error || !journey) {
    return (
      <EmptyState
        title="Journey not found"
        description={String(journeyQuery.error ?? "Unknown journey")}
        action={
          <Button variant="outline" asChild>
            <Link to="/journeys">Back to journeys</Link>
          </Button>
        }
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <Button variant="ghost" size="sm" asChild className="-ml-2">
            <Link to="/journeys">
              <ArrowLeft className="h-4 w-4" />
              Journeys
            </Link>
          </Button>
          <h2 className="text-xl font-semibold">{journey.name}</h2>
          <p className="text-sm text-muted-foreground max-w-2xl">{journey.description}</p>
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <StatusBadge status={journey.status} />
            <span className="text-xs font-mono text-muted-foreground">{journey.id}</span>
            <span
              className={cn(
                "text-xs px-2 py-0.5 rounded-full border",
                stream.sseStatus === "connected" && "border-emerald-500/50 text-emerald-400",
                stream.sseStatus === "connecting" && "border-amber-500/50 text-amber-400",
                stream.sseStatus === "disconnected" && "border-red-500/50 text-red-400",
                stream.sseStatus === "idle" && "border-border text-muted-foreground",
              )}
              data-testid="sse-status"
            >
              SSE: {stream.sseStatus}
            </span>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {!isRunning ? (
            <Button
              size="sm"
              disabled={isPipelineRunning || journey.stages.length === 0}
              onClick={() => void startPipeline()}
              data-testid="start-pipeline"
            >
              <Play className="h-4 w-4" />
              Start processing ({journey.stages.length} stages)
            </Button>
          ) : null}
          {isRunning && activeJobId ? (
            <Button size="sm" variant="destructive" disabled={cancelMut.isPending} onClick={() => cancelMut.mutate()}>
              <Square className="h-4 w-4" />
              Cancel
            </Button>
          ) : null}
          <Button variant="outline" size="sm" onClick={() => journeyQuery.refetch()}>
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
        </div>
      </div>

      {pipelineError ? (
        <div className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-300">
          Pipeline stopped: {pipelineError}
        </div>
      ) : null}

      <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
        <span>{journey.summary.totalJobs} jobs</span>
        <span className="text-emerald-400">{journey.summary.completedJobs} completed</span>
        <span className="text-blue-400">{journey.summary.runningJobs} running</span>
        <span className="text-red-400">{journey.summary.failedJobs} failed</span>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(260px,340px)_1fr] lg:items-start">
        <WorkflowTree
          stages={journey.stages}
          stageStatus={stageStatus}
          stepStatus={stepStatusFn}
          logCount={logCount}
          expandedStages={expandedStages}
          selectedStep={selectedStep}
          onToggleStage={(stageId) =>
            setExpandedStages((prev) => ({ ...prev, [stageId]: !prev[stageId] }))
          }
          onSelectStep={(stageId, stepId) => {
            setSelectedStep({ stageId, stepId });
            setSelectedStageId(stageId);
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
                    if (selectedStep) {
                      stream.setLevelFilter((prev) => ({
                        ...prev,
                        [stepKey(selectedStep.stageId, selectedStep.stepId)]: lv,
                      }));
                    }
                  }}
                  variant="panel"
                />
              </div>
            </>
          ) : (
            <div className="flex flex-1 items-center justify-center p-8 text-sm text-muted-foreground">
              Select a step in the workflow tree to view logs
            </div>
          )}
        </div>
      </div>

      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between gap-2">
            <CardTitle className="text-base">Job history</CardTitle>
            <Link to="/executions" className="text-xs text-primary hover:underline">
              View all executions
            </Link>
          </div>
        </CardHeader>
        <CardContent>
          {journey.jobs.length === 0 ? (
            <EmptyState title="No jobs yet" description="Start processing to run the full journey pipeline." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-muted-foreground border-b border-border">
                    <th className="py-2 pr-4">Job</th>
                    <th className="py-2 pr-4">Scope</th>
                    <th className="py-2 pr-4">Started</th>
                    <th className="py-2">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {journey.jobs.map((job) => (
                    <tr
                      key={job.id}
                      className={cn(
                        "border-b border-border/50 cursor-pointer hover:bg-accent/50",
                        activeJobId === job.id && "bg-accent/30",
                      )}
                      onClick={() => watchJob(job)}
                    >
                      <td className="py-2 pr-4">
                        <Link
                          to={`/executions/stage/${journey.id}/${job.id}`}
                          className="text-primary hover:underline font-mono"
                          onClick={(e) => e.stopPropagation()}
                        >
                          {job.id}
                        </Link>
                      </td>
                      <td className="py-2 pr-4">{jobStageLabel(job)}</td>
                      <td className="py-2 pr-4 text-muted-foreground">{job.startedAt ?? "—"}</td>
                      <td className="py-2">
                        <StatusBadge status={job.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <BatchSchedulesPanel
        journeyId={journey.id}
        journeyName={journey.name}
        stages={journey.stages.map((stage) => ({ id: stage.id, name: stage.name }))}
      />

      <ArchivedJobsSearch />
    </div>
  );
}
