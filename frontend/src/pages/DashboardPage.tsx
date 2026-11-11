import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { EngineFlow } from "@/components/dashboard/EngineFlow";
import { CHART_MARGIN, ChartLegend, ChartTooltip, STATUS_COLORS, axisProps, barProps, cursorBand, gridProps, seriesColor } from "@/components/ds/charts";
import { EmptyState, PageHeader, Panel, SkeletonRows, StatusPill } from "@/components/ds/kit";
import { WorkerHealthCardLink, WorkerHealthList } from "@/components/workers/WorkerHealthList";
import { useWorkersSnapshot } from "@/hooks/useQueueSnapshot";
import { api } from "@/services/api";
import { truncateId } from "@/lib/utils";
import { relativeTime } from "@/utils/time";
import type { UnifiedRunRow } from "@/types/stageJourney";

const OK = ["completed", "succeeded", "success"];
const BAD = ["failed", "error"];

function throughputFromRuns(runs: UnifiedRunRow[], hours = 24) {
  const cutoff = Date.now() - hours * 60 * 60 * 1000;
  let submitted = 0;
  let succeeded = 0;
  let failed = 0;
  for (const run of runs) {
    if (run.kind === "stage_job") {
      const ts = run.startedAt ? Date.parse(run.startedAt) : NaN;
      if (!Number.isFinite(ts) || ts < cutoff) continue;
    } else {
      continue;
    }
    submitted += 1;
    const status = run.status.toLowerCase();
    if (OK.includes(status)) succeeded += 1;
    else if (BAD.includes(status)) failed += 1;
  }
  return { submitted, succeeded, failed };
}

/** Runs per hour for the last 24 hours, oldest first. */
function hourlyFromRuns(runs: UnifiedRunRow[]) {
  const now = new Date();
  now.setMinutes(0, 0, 0);
  const buckets = Array.from({ length: 24 }, (_, i) => {
    const start = now.getTime() - (23 - i) * 3_600_000;
    return { start, hour: new Date(start).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }), succeeded: 0, failed: 0, other: 0 };
  });
  for (const run of runs) {
    if (run.kind !== "stage_job" || !run.startedAt) continue;
    const ts = Date.parse(run.startedAt);
    if (!Number.isFinite(ts)) continue;
    const idx = Math.floor((ts - buckets[0].start) / 3_600_000);
    if (idx < 0 || idx > 23) continue;
    const status = run.status.toLowerCase();
    if (OK.includes(status)) buckets[idx].succeeded += 1;
    else if (BAD.includes(status)) buckets[idx].failed += 1;
    else buckets[idx].other += 1;
  }
  return buckets;
}

function runHref(run: UnifiedRunRow) {
  return run.kind === "stage_job" ? `/executions/stage/${run.journeyId}/${run.id}` : `/executions/${run.id}`;
}

export function DashboardPage() {
  const fleet = useQuery({
    queryKey: ["fleet", "summary"],
    queryFn: () => api.fleetSummary(),
    refetchInterval: 2_000,
  });
  const metrics = useQuery({
    queryKey: ["fleet", "metrics"],
    queryFn: () => api.fleetMetrics("24h"),
    refetchInterval: 30_000,
  });
  const queueWorkers = useWorkersSnapshot();
  const running = useQuery({
    queryKey: ["executions", "RUNNING"],
    queryFn: () => api.listExecutions({ status: "running" }),
    refetchInterval: 5_000,
  });
  const journeys = useQuery({
    queryKey: ["simple-journeys"],
    queryFn: () => api.listSimpleJourneys(),
    refetchInterval: 10_000,
  });
  const recentRuns = useQuery({
    queryKey: ["runs"],
    queryFn: () => api.listAllRuns(),
    refetchInterval: 5_000,
  });

  const summary = fleet.data;
  const runThroughput = useMemo(() => throughputFromRuns(recentRuns.data ?? []), [recentRuns.data]);
  const throughput =
    runThroughput.submitted > 0 || runThroughput.failed > 0 || runThroughput.succeeded > 0
      ? runThroughput
      : metrics.data?.throughput;
  const hourly = useMemo(() => {
    const fromApi = metrics.data?.timeline ?? [];
    if (fromApi.length > 0) {
      return fromApi.map((t) => ({
        hour: new Date(t.hour).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        succeeded: t.succeeded,
        failed: t.failed,
        other: 0,
      }));
    }
    return hourlyFromRuns(recentRuns.data ?? []);
  }, [metrics.data?.timeline, recentRuns.data]);
  const hasHourly = hourly.some((h) => h.succeeded + h.failed + h.other > 0);

  const p95 = metrics.data?.tool_dispatch_p95_ms;
  const journeyRows = journeys.data ?? [];
  const journeyJobTotal = journeyRows.reduce((n, j) => n + Number(j.totalJobs ?? 0), 0);
  const recent = (recentRuns.data ?? []).slice(0, 8);
  const stageActive = summary?.stage_jobs_active ?? 0;
  const stageQueued = summary?.stage_jobs_queued ?? 0;
  const dslActive = summary?.dsl_executions_active ?? 0;
  const dslQueued = summary?.dsl_executions_queued ?? 0;
  const jobWorkerRows = queueWorkers.workers.data?.workers ?? [];
  const jobWorkerCount = jobWorkerRows.length;
  const desired = queueWorkers.summary.data?.replicas;
  const failedNow = summary?.failed ?? 0;
  const throughputReady = !recentRuns.isLoading;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        description="Fleet health, journey activity, and recent executions in one view."
        meta={
          failedNow > 0 ? (
            <StatusPill tone="danger" variant="soft">{failedNow} failed</StatusPill>
          ) : fleet.isLoading ? null : (
            <StatusPill tone="success" variant="soft">No failed jobs</StatusPill>
          )
        }
      />

      <EngineFlow
        journeys={journeys.isLoading ? "…" : journeyRows.length}
        journeyJobs={`${journeyJobTotal.toLocaleString()} total stage jobs`}
        queued={<span data-testid="queued-execution-count">{fleet.isLoading ? "…" : (summary?.queued ?? 0)}</span>}
        queuedNumber={summary?.queued ?? 0}
        queueHint={stageQueued > 0 || dslQueued > 0 ? `${stageQueued} stage · ${dslQueued} DSL waiting` : "Nothing waiting"}
        active={<span data-testid="active-execution-count">{fleet.isLoading ? "…" : (summary?.active ?? 0)}</span>}
        activeNumber={summary?.active ?? 0}
        limit={summary?.global_limit}
        workersHint={
          <>
            Limit {summary?.global_limit ?? "—"}
            {summary?.running_counter != null ? ` · counter ${summary.running_counter}` : ""}
            {stageActive > 0 || dslActive > 0 ? ` · ${stageActive} stage · ${dslActive} DSL` : ""}
            {" · "}
            <span data-testid="job-worker-count">{queueWorkers.workers.isLoading ? "…" : jobWorkerCount}</span> job-worker pods
            {desired != null ? ` · ${desired} desired` : ""}
          </>
        }
        succeeded={throughput?.succeeded ?? 0}
        failed={throughput?.failed ?? 0}
        resultsReady={throughputReady}
      />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Panel
          title="24h throughput"
          description="Stage jobs started per hour, by outcome."
          actions={
            <ChartLegend
              items={[
                { label: "Succeeded", color: seriesColor(0), value: (throughput?.succeeded ?? 0).toLocaleString() },
                { label: "Failed", color: STATUS_COLORS.danger, value: (throughput?.failed ?? 0).toLocaleString() },
                { label: "Submitted", color: STATUS_COLORS.neutral, value: (throughput?.submitted ?? 0).toLocaleString() },
              ]}
            />
          }
          footer={
            <span data-testid="tool-dispatch-p95">
              Tool dispatch p95:{" "}
              <span className="num font-medium text-foreground">
                {p95 != null ? `${p95.toFixed(1)} ms` : metrics.isLoading ? "…" : "n/a"}
              </span>
            </span>
          }
        >
          {!throughputReady ? (
            <SkeletonRows rows={5} className="p-0" />
          ) : !hasHourly ? (
            <EmptyState bare icon="chart-bar" title="No runs in the last 24 hours" description="Hourly throughput appears here once jobs start." className="py-8" />
          ) : (
            <div className="h-[220px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={hourly} margin={CHART_MARGIN}>
                  <CartesianGrid {...gridProps} />
                  <XAxis dataKey="hour" {...axisProps} interval={3} />
                  <YAxis {...axisProps} width={36} allowDecimals={false} />
                  <Tooltip content={<ChartTooltip />} cursor={cursorBand} />
                  <Bar dataKey="succeeded" name="Succeeded" stackId="runs" fill={seriesColor(0)} {...barProps} radius={[0, 0, 0, 0]} />
                  <Bar dataKey="other" name="In progress" stackId="runs" fill={STATUS_COLORS.neutral} {...barProps} radius={[0, 0, 0, 0]} />
                  <Bar dataKey="failed" name="Failed" stackId="runs" fill={STATUS_COLORS.danger} {...barProps} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Panel>

        <Panel title="Worker health" actions={<WorkerHealthCardLink />} flush>
          <WorkerHealthList
            workers={jobWorkerRows.map((w) => ({
              worker_id: w.worker_id,
              role: "job-worker",
              status: w.status,
              last_seen: w.last_seen,
            }))}
            loading={queueWorkers.workers.isLoading}
            emptyTitle="No job workers"
            emptyDescription="Job-worker pods and Redis consumers appear here."
          />
        </Panel>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Panel
          title="Recent runs"
          flush
          actions={
            <Link to="/executions" className="link text-sm">
              View all
            </Link>
          }
        >
          {recentRuns.isLoading ? (
            <SkeletonRows rows={6} />
          ) : recent.length === 0 ? (
            <EmptyState
              bare
              icon="play"
              title="No runs yet"
              description="Start a stage job from Journeys or submit a DSL execution."
              action={
                <Link to="/journeys" className="link">
                  Open journeys
                </Link>
              }
            />
          ) : (
            <div className="scroll-thin overflow-x-auto">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Journey</th>
                    <th>Run</th>
                    <th>Started</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {recent.map((run) => (
                    <tr key={`${run.kind}-${run.journeyId}-${run.id}`}>
                      <td className="max-w-[320px]">
                        <Link to={runHref(run)} className="block truncate font-medium text-foreground hover:text-primary dark:hover:text-brand-hi">
                          {run.kind === "stage_job" ? run.journeyName ?? run.journeyId : run.journeyId}
                        </Link>
                        <span className="text-xs text-muted-foreground">
                          {run.kind === "stage_job" ? (run.jobType === "journey" ? "Full journey" : run.stageId ? `Stage ${run.stageId}` : "Stage job") : "DSL execution"}
                        </span>
                      </td>
                      <td>
                        <Link to={runHref(run)} className="mono-id hover:text-foreground" title={run.id}>
                          {truncateId(run.id, 14)}
                        </Link>
                      </td>
                      <td className="whitespace-nowrap text-muted-foreground">
                        {run.kind === "stage_job" && run.startedAt ? relativeTime(run.startedAt) : "—"}
                      </td>
                      <td>
                        <StatusPill status={run.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>

        <Panel title="DSL executions running" flush>
          {running.isLoading ? (
            <SkeletonRows rows={3} />
          ) : (running.data?.length ?? 0) === 0 ? (
            <EmptyState bare title="No active DSL executions" description="DSL runs appear here when submitted from the YAML studio." />
          ) : (
            <ul className="divide-y divide-border">
              {running.data!.map((ex) => (
                <li key={ex.execution_id} className="flex items-center justify-between gap-3 px-4 py-2.5 sm:px-5">
                  <div className="min-w-0">
                    <Link to={`/executions/${ex.execution_id}`} className="block truncate font-mono text-sm text-foreground hover:text-primary dark:hover:text-brand-hi">
                      {truncateId(ex.execution_id)}
                    </Link>
                    <span className="block truncate text-xs text-muted-foreground">{ex.journey_id}</span>
                  </div>
                  <StatusPill status={ex.status} />
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  );
}
