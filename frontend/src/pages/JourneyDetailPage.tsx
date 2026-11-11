import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ArchivedJobsSearch } from "@/components/schedules/ArchivedJobsSearch";
import { BatchSchedulesPanel } from "@/components/schedules/BatchSchedulesPanel";
import { StepConsole } from "@/components/stage/StepConsole";
import { WorkflowTree, type SelectedStep } from "@/components/stage/WorkflowTree";
import { Icon } from "@/components/ds/Icon";
import { EmptyState, InlineError, LineTabs, MetricStrip, PageHeader, SkeletonRows, StatusPill, TableShell, type Tone } from "@/components/ds/kit";
import { Button } from "@/components/ui/button";
import { STEP_PENDING, useJourneyJobStream } from "@/hooks/useJourneyJobStream";
import { relativeTime } from "@/utils/time";
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
  const [tab, setTab] = useState<"history" | "schedules" | "archive">("history");
  const [historyLimit, setHistoryLimit] = useState(25);

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

  // Open on the first step so the log console is never blank.
  useEffect(() => {
    if (selectedStep || orderedStages.length === 0) return;
    const first = orderedStages[0];
    const step = first.steps[0];
    if (!step) return;
    setSelectedStep({ stageId: first.id, stepId: step.id });
    void loadHistoricalStepLogs(first.id, step.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orderedStages, selectedStep]);

  if (journeyQuery.isLoading) {
    return (
      <TableShell>
        <SkeletonRows rows={8} />
      </TableShell>
    );
  }
  if (journeyQuery.error || !journey) {
    return (
      <EmptyState
        icon="route"
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

  const sseTone: Record<string, Tone> = { connected: "success", connecting: "warning", disconnected: "danger", idle: "neutral" };
  const liveStatus = isRunning ? "running" : journey.status.toLowerCase() === "pending" ? null : journey.status;
  const visibleJobs = journey.jobs.slice(0, historyLimit);

  return (
    <div className="space-y-5">
      <PageHeader
        back={
          <Link to="/journeys" className="inline-flex items-center gap-1 text-muted-foreground transition-colors hover:text-foreground">
            <Icon name="chevron-left" className="h-3.5 w-3.5" />
            Journeys
          </Link>
        }
        title={journey.name}
        description={journey.description}
        meta={
          <>
            {liveStatus ? <StatusPill status={liveStatus} variant="soft" /> : <StatusPill tone="neutral" variant="soft">Idle</StatusPill>}
            <span className="mono-id">{journey.id}</span>
            <StatusPill tone={sseTone[stream.sseStatus] ?? "neutral"} live={stream.sseStatus === "connected"} data-testid="sse-status" className="font-normal text-muted-foreground">
              SSE: {stream.sseStatus}
            </StatusPill>
          </>
        }
        actions={
          <>
            <Button variant="outline" size="sm" onClick={() => journeyQuery.refetch()}>
              <Icon name="refresh" className={journeyQuery.isFetching ? "animate-spin" : undefined} />
              Refresh
            </Button>
            {isRunning && activeJobId ? (
              <Button size="sm" variant="destructive" disabled={cancelMut.isPending} onClick={() => cancelMut.mutate()}>
                <Icon name="close" className="h-3 w-3" />
                Cancel
              </Button>
            ) : null}
            {!isRunning ? (
              <Button
                size="sm"
                disabled={isPipelineRunning || journey.stages.length === 0}
                onClick={() => void startPipeline()}
                data-testid="start-pipeline"
              >
                <Icon name="play" />
                Start processing ({journey.stages.length} {journey.stages.length === 1 ? "stage" : "stages"})
              </Button>
            ) : null}
          </>
        }
      />

      {pipelineError ? <InlineError>Pipeline stopped: {pipelineError}</InlineError> : null}

      <MetricStrip
        items={[
          { label: "Jobs", value: journey.summary.totalJobs.toLocaleString(), hint: `${journey.stages.length} ${journey.stages.length === 1 ? "stage" : "stages"} per run` },
          { label: "Completed", value: journey.summary.completedJobs.toLocaleString(), hint: journey.summary.totalJobs > 0 ? `${((journey.summary.completedJobs / journey.summary.totalJobs) * 100).toFixed(1)}% of all jobs` : undefined },
          { label: "Running", value: journey.summary.runningJobs.toLocaleString(), hint: activeJobId ? `Watching ${activeJobId}` : "Nothing in flight" },
          { label: "Failed", value: journey.summary.failedJobs.toLocaleString(), tone: journey.summary.failedJobs > 0 ? "danger" : undefined },
        ]}
      />

      <div className="grid gap-4 lg:grid-cols-[minmax(260px,340px)_minmax(0,1fr)] lg:items-stretch">
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

        <section className="flex min-h-[460px] min-w-0 flex-col overflow-hidden rounded-xl border border-border bg-card shadow-xs">
          {selectedStepMeta ? (
            <>
              <header className="flex min-h-[52px] flex-col justify-center border-b border-border px-4 py-2 sm:px-5">
                <h3 className="truncate text-md font-medium text-foreground">{selectedStepMeta.step.name}</h3>
                <p className="truncate text-xs text-muted-foreground">
                  {selectedStepMeta.stage.name}
                  {selectedStepMeta.step.description ? ` · ${selectedStepMeta.step.description}` : ""}
                </p>
              </header>
              <div className="min-h-0 flex-1">
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
            <EmptyState
              bare
              icon="terminal"
              className="flex-1"
              title="Step logs"
              description="Select a step in the workflow tree to view logs"
            />
          )}
        </section>
      </div>

      <div className="space-y-4 pt-1">
        <LineTabs
          label="Journey records"
          value={tab}
          onChange={setTab}
          tabs={[
            { value: "history", label: "Job history", icon: "history", count: journey.jobs.length },
            { value: "schedules", label: "Schedules", icon: "calendar" },
            { value: "archive", label: "Archived jobs", icon: "folder" },
          ]}
          actions={
            <Link to="/executions" className="link text-sm">
              View all executions
            </Link>
          }
        />

        {tab === "history" ? (
          journey.jobs.length === 0 ? (
            <EmptyState icon="history" title="No jobs yet" description="Start processing to run the full journey pipeline." />
          ) : (
            <>
              <TableShell>
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>Job</th>
                      <th>Scope</th>
                      <th>Started</th>
                      <th>Status</th>
                      <th className="r">Logs</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleJobs.map((job) => (
                      <tr
                        key={job.id}
                        className={activeJobId === job.id ? "cursor-pointer !bg-primary/5" : "cursor-pointer"}
                        onClick={() => watchJob(job)}
                      >
                        <td>
                          <Link
                            to={`/executions/stage/${journey.id}/${job.id}`}
                            className="link font-mono text-xs"
                            onClick={(e) => e.stopPropagation()}
                          >
                            {job.id}
                          </Link>
                        </td>
                        <td>{jobStageLabel(job)}</td>
                        <td className="whitespace-nowrap text-muted-foreground" title={job.startedAt ?? undefined}>
                          {job.startedAt ? relativeTime(job.startedAt) : "—"}
                        </td>
                        <td>
                          <StatusPill status={job.status} />
                        </td>
                        <td className="r text-xs text-muted-foreground">
                          {activeJobId === job.id ? <span className="text-primary dark:text-brand-hi">Showing above</span> : "Click to view"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableShell>
              {journey.jobs.length > historyLimit ? (
                <div className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
                  <span>Showing {historyLimit} of {journey.jobs.length.toLocaleString()}</span>
                  <Button variant="outline" size="sm" onClick={() => setHistoryLimit((n) => n + 50)}>
                    Show 50 more
                  </Button>
                </div>
              ) : null}
            </>
          )
        ) : null}

        {tab === "schedules" ? (
          <BatchSchedulesPanel
            journeyId={journey.id}
            journeyName={journey.name}
            stages={journey.stages.map((stage) => ({ id: stage.id, name: stage.name }))}
          />
        ) : null}

        {tab === "archive" ? <ArchivedJobsSearch /> : null}
      </div>
    </div>
  );
}
