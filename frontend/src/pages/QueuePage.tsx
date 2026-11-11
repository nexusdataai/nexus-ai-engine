import { Link } from "react-router-dom";

import { Icon } from "@/components/ds/Icon";
import { EmptyState, LiveBadge, MetricStrip, PageHeader, Panel, SkeletonRows, StatusPill } from "@/components/ds/kit";
import { QueueVisualization } from "@/components/queue/QueueVisualization";
import { Button } from "@/components/ui/button";
import { shortWorkerName } from "@/components/workers/WorkerHealthList";
import { useQueueSnapshot } from "@/hooks/useQueueSnapshot";
import { cn, truncateId } from "@/lib/utils";
import type { QueueJob } from "@/types/api";

function jobHref(job: QueueJob): string {
  if (job.job_kind === "dsl_execution") {
    return `/executions/${job.job_id}`;
  }
  return `/executions/stage/${job.journey_id}/${job.job_id}`;
}

function waitedFor(job: QueueJob): string {
  if (!job.enqueued_at) return "—";
  const ms = job.enqueued_at > 1e12 ? job.enqueued_at : job.enqueued_at * 1000;
  const sec = Math.max(0, Math.floor((Date.now() - ms) / 1000));
  if (sec < 60) return `${sec}s`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m ${sec % 60}s`;
  return `${Math.floor(sec / 3600)}h ${Math.floor((sec % 3600) / 60)}m`;
}

export function QueuePage() {
  const { summary, jobs, live, refresh, isRefreshing } = useQueueSnapshot();

  if (summary.isError || jobs.isError) {
    const message =
      (summary.error as Error)?.message ||
      (jobs.error as Error)?.message ||
      "Queue API unavailable";
    return (
      <div className="space-y-6">
        <PageHeader title="Job Queue" description="Live Redis job pipeline." />
        <EmptyState
          icon="layers"
          title="Queue unavailable"
          description={
            message.includes("503") || message.includes("queue")
              ? "Queue mode requires JOB_EXECUTION_MODE=queue and Redis. Enable queue mode in your deployment."
              : message
          }
          action={
            <Link to="/workers" className="link">
              Open workers
            </Link>
          }
        />
      </div>
    );
  }

  const snap = summary.data;
  const rows = jobs.data?.jobs ?? [];
  const waitingCount = rows.filter((j) => j.state === "waiting" || j.state === "claimed").length;
  const claimedCount = rows.filter((j) => j.state === "claimed").length;
  const active = snap?.active ?? 0;
  const max = snap?.max_global;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Job Queue"
        description="Live view of waiting, claimed, and running jobs in the Redis stream pipeline."
        actions={
          <>
            <LiveBadge live={live} data-testid="queue-sse-status" className="mr-1" />
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={isRefreshing}
              onClick={() => void refresh()}
              data-testid="queue-refresh"
            >
              <Icon name="refresh" className={cn(isRefreshing && "animate-spin")} />
              Refresh
            </Button>
          </>
        }
      />

      <MetricStrip
        columns={5}
        items={[
          { label: "Waiting", value: jobs.isLoading ? "…" : waitingCount, hint: "In line for a slot", tone: waitingCount > 0 ? "warning" : undefined },
          { label: "Claimed", value: jobs.isLoading ? "…" : claimedCount, hint: "Picked up, not started" },
          { label: "Running", value: summary.isLoading ? "…" : active, testId: "queue-running-count", hint: "Executing now" },
          {
            label: "Capacity",
            value: summary.isLoading ? "…" : `${active} / ${max ?? "—"}`,
            hint: max ? `${Math.round((active / max) * 100)}% of the global limit` : undefined,
          },
          {
            label: "Stream lag",
            value: summary.isLoading ? "…" : (snap?.lag ?? 0),
            hint: `${snap?.consumer_count ?? "—"} consumers${snap?.worker_threads != null ? ` · ${snap.worker_threads} threads each` : ""}`,
          },
        ]}
      />

      <Panel title="Pipeline" description="Jobs move from the waiting lane into a free running slot.">
        {jobs.isLoading ? (
          <SkeletonRows rows={3} className="p-0" />
        ) : (
          <QueueVisualization jobs={rows} maxGlobal={snap?.max_global ?? 10} activeFromSummary={snap?.active} />
        )}
      </Panel>

      <Panel title="Queue jobs" description={rows.length > 0 ? `${rows.length} in the stream` : undefined} flush>
        {jobs.isLoading ? (
          <SkeletonRows rows={4} />
        ) : rows.length === 0 ? (
          <EmptyState bare icon="check-circle" title="Queue empty" description="Submit journey or DSL jobs to see them here." />
        ) : (
          <div className="scroll-thin overflow-x-auto">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Job</th>
                  <th>Journey</th>
                  <th>Kind</th>
                  <th>State</th>
                  <th>Waited</th>
                  <th>Worker</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((job) => (
                  <tr key={job.stream_id}>
                    <td>
                      <Link to={jobHref(job)} className="link font-mono text-xs" title={job.job_id}>
                        {truncateId(job.job_id, 16)}
                      </Link>
                    </td>
                    <td>
                      <Link to={`/journeys/${job.journey_id}`} className="mono-id hover:text-foreground" title={job.journey_id}>
                        {truncateId(job.journey_id, 12)}
                      </Link>
                    </td>
                    <td className="text-muted-foreground">{job.job_kind.replace(/_/g, " ")}</td>
                    <td>
                      <StatusPill status={job.state === "running" ? "RUNNING" : job.state === "claimed" ? "CLAIMED" : "PENDING"} live={job.state === "running"}>
                        {job.state}
                      </StatusPill>
                    </td>
                    <td className="num whitespace-nowrap text-muted-foreground">{waitedFor(job)}</td>
                    <td className="max-w-[200px] truncate font-mono text-xs text-muted-foreground" title={job.consumer_name ?? undefined}>
                      {job.consumer_name ? shortWorkerName(job.consumer_name.replace(/-[0-9a-f]{6}$/, "")) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}
