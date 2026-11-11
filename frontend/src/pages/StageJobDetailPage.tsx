import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { StepConsole } from "@/components/stage/StepConsole";
import { WorkflowTree, type SelectedStep } from "@/components/stage/WorkflowTree";
import { Icon } from "@/components/ds/Icon";
import { EmptyState, KeyValues, Meter, PageHeader, SkeletonRows, StatusPill, TableShell, toneOf, type Tone } from "@/components/ds/kit";
import { STEP_PENDING, useJourneyJobStream } from "@/hooks/useJourneyJobStream";
import { relativeTime } from "@/utils/time";
import { api } from "@/services/api";
import type { LogEntry, StepStatus } from "@/types/stageJobStream";

function stepKey(stageId: string, stepId: string): string {
  return `${stageId}:${stepId}`;
}

export function StageJobDetailPage() {
  const { journeyId = "", jobId = "" } = useParams();
  const queryClient = useQueryClient();
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

  const journey = journeyQuery.data;
  // Some engines answer 404 for the single-job endpoint even though the job is
  // in the journey's job list; fall back to that record so the page still opens.
  const job = jobQuery.data ?? journey?.jobs.find((j) => j.id === jobId);

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

  const onJobStreamComplete = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["stage-job", journeyId, jobId] });
    void queryClient.invalidateQueries({ queryKey: ["stage-journey", journeyId] });
  }, [queryClient, journeyId, jobId]);

  const stream = useJourneyJobStream(journeyId, stages, jobId, job?.status ?? null, onJobStreamComplete);

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

  const back = (
    <Link to={`/journeys/${journeyId}`} className="inline-flex items-center gap-1 text-muted-foreground transition-colors hover:text-foreground">
      <Icon name="chevron-left" className="h-3.5 w-3.5" />
      Back to journey
    </Link>
  );

  if (jobQuery.isLoading || (!job && journeyQuery.isLoading)) {
    return (
      <div className="space-y-5">
        <div className="text-sm">{back}</div>
        <TableShell>
          <SkeletonRows rows={8} />
        </TableShell>
      </div>
    );
  }
  if (!job) {
    return (
      <div className="space-y-5">
        <div className="text-sm">{back}</div>
        <EmptyState icon="play" title="Job not found" description={String(jobQuery.error ?? "Unknown job")} />
      </div>
    );
  }

  const sseLabel = terminal ? "finished" : stream.sseStatus;
  const sseTone: Record<string, Tone> = { connected: "success", connecting: "warning", disconnected: "danger", idle: "neutral", finished: "neutral" };
  const jobTone = toneOf(job.status);

  return (
    <div className="space-y-5">
      <PageHeader
        back={back}
        title={<span className="font-mono text-lg">{job.id}</span>}
        description={
          <>
            {scopeLabel} ·{" "}
            <Link to={`/journeys/${journeyId}`} className="link">
              {journey?.name ?? journeyId}
            </Link>
          </>
        }
        meta={
          <>
            <StatusPill status={job.status} variant="soft" />
            <StatusPill tone={sseTone[sseLabel] ?? "neutral"} live={sseLabel === "connected"} data-testid="sse-status" className="font-normal text-muted-foreground">
              SSE: {sseLabel}
            </StatusPill>
          </>
        }
      />

      <div className="grid gap-x-10 gap-y-4 rounded-xl border border-border bg-card p-4 shadow-xs sm:p-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <div>
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-sm text-muted-foreground">Progress</span>
            <span className="num text-2xl font-medium tracking-tight text-foreground">{Math.round(job.progress)}%</span>
          </div>
          <Meter value={job.progress} tone={jobTone === "danger" ? "danger" : jobTone === "success" ? "success" : "info"} className="mt-2" label="Job progress" />
        </div>
        <KeyValues
          columns={2}
          items={[
            { label: "Started", value: job.startedAt ? <span title={job.startedAt}>{relativeTime(job.startedAt)}</span> : "—" },
            { label: "Duration", value: job.duration ?? "—" },
            { label: "Triggered by", value: job.triggeredBy ?? "—" },
            { label: "Stages", value: stages.length },
          ]}
        />
      </div>

      {stages.length === 0 ? (
        <EmptyState icon="workflow" title="No stages" description="No stage metadata found for this job." />
      ) : (
        <div className="grid gap-4 lg:grid-cols-[minmax(260px,340px)_minmax(0,1fr)] lg:items-stretch">
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
              <EmptyState bare icon="terminal" className="flex-1" title="Step logs" description="Select a step to view logs" />
            )}
          </section>
        </div>
      )}
    </div>
  );
}
