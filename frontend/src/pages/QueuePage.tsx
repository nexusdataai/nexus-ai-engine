import { Link } from "react-router-dom";

import { EmptyState } from "@/components/EmptyState";
import { QueueVisualization } from "@/components/queue/QueueVisualization";
import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useQueueSnapshot } from "@/hooks/useQueueSnapshot";
import { truncateId } from "@/lib/utils";
import type { QueueJob } from "@/types/api";

function jobHref(job: QueueJob): string {
  if (job.job_kind === "dsl_execution") {
    return `/executions/${job.job_id}`;
  }
  return `/executions/stage/${job.journey_id}/${job.job_id}`;
}

export function QueuePage() {
  const { summary, jobs } = useQueueSnapshot();

  if (summary.isError || jobs.isError) {
    const message =
      (summary.error as Error)?.message ||
      (jobs.error as Error)?.message ||
      "Queue API unavailable";
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold">Job Queue</h2>
          <p className="text-sm text-muted-foreground">Live Redis job pipeline.</p>
        </div>
        <EmptyState
          title="Queue unavailable"
          description={
            message.includes("503") || message.includes("queue")
              ? "Queue mode requires JOB_EXECUTION_MODE=queue and Redis. Enable queue mode in your deployment."
              : message
          }
          action={
            <Link to="/workers" className="text-sm text-primary hover:underline">
              Open workers
            </Link>
          }
        />
      </div>
    );
  }

  const snap = summary.data;
  const rows = jobs.data?.jobs ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Job Queue</h2>
        <p className="text-sm text-muted-foreground">
          Live view of waiting, claimed, and running jobs in the Redis stream pipeline.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Waiting</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">{summary.isLoading ? "…" : (snap?.lag ?? 0)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Claimed</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">
              {jobs.isLoading ? "…" : rows.filter((j) => j.state === "claimed").length}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Running</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold" data-testid="queue-running-count">
              {summary.isLoading ? "…" : (snap?.active ?? 0)}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Capacity</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">
              {summary.isLoading ? "…" : `${snap?.active ?? 0} / ${snap?.max_global ?? "—"}`}
            </p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Pipeline</CardTitle>
        </CardHeader>
        <CardContent>
          {jobs.isLoading ? (
            <p className="text-sm text-muted-foreground">Loading queue…</p>
          ) : (
            <QueueVisualization jobs={rows} maxGlobal={snap?.max_global ?? 10} />
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Queue jobs</CardTitle>
        </CardHeader>
        <CardContent>
          {jobs.isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : rows.length === 0 ? (
            <EmptyState title="Queue empty" description="Submit journey or DSL jobs to see them here." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-muted-foreground">
                    <th className="py-2 pr-4">Job</th>
                    <th className="py-2 pr-4">Journey</th>
                    <th className="py-2 pr-4">Kind</th>
                    <th className="py-2 pr-4">State</th>
                    <th className="py-2 pr-4">Worker</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((job) => (
                    <tr key={job.stream_id} className="border-b border-border/60">
                      <td className="py-2 pr-4">
                        <Link to={jobHref(job)} className="font-mono text-primary hover:underline">
                          {truncateId(job.job_id, 16)}
                        </Link>
                      </td>
                      <td className="py-2 pr-4 font-mono text-muted-foreground">
                        {truncateId(job.journey_id, 12)}
                      </td>
                      <td className="py-2 pr-4">{job.job_kind}</td>
                      <td className="py-2 pr-4">
                        <StatusBadge status={job.state === "running" ? "RUNNING" : "PENDING"} />
                      </td>
                      <td className="py-2 pr-4 text-xs text-muted-foreground truncate max-w-[180px]">
                        {job.consumer_name ?? "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
