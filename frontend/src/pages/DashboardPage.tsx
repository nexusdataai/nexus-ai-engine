import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Activity, AlertTriangle, Clock, PlayCircle, Server, Users } from "lucide-react";

import { EmptyState } from "@/components/EmptyState";
import { StatusBadge } from "@/components/StatusBadge";
import { WorkerHealthCardLink, WorkerHealthList } from "@/components/workers/WorkerHealthList";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/services/api";
import { truncateId } from "@/lib/utils";

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
  const workers = useQuery({
    queryKey: ["fleet", "workers"],
    queryFn: () => api.fleetWorkers(),
    refetchInterval: 10_000,
  });
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
  const throughput = metrics.data?.throughput;
  const p95 = metrics.data?.tool_dispatch_p95_ms;
  const journeyRows = journeys.data ?? [];
  const journeyJobTotal = journeyRows.reduce((n, j) => n + Number(j.totalJobs ?? 0), 0);
  const recent = (recentRuns.data ?? []).slice(0, 8);
  const stageActive = summary?.stage_jobs_active ?? 0;
  const stageQueued = summary?.stage_jobs_queued ?? 0;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Dashboard</h2>
        <p className="text-sm text-muted-foreground">
          Fleet health, journey activity, and recent executions in one view.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Journeys</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">{journeys.isLoading ? "…" : journeyRows.length}</p>
            <p className="text-xs text-muted-foreground mt-1">{journeyJobTotal} total stage jobs</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <PlayCircle className="h-4 w-4 text-blue-400" />
              Active executions
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold" data-testid="active-execution-count">
              {fleet.isLoading ? "…" : (summary?.active ?? 0)}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Limit {summary?.global_limit ?? "—"}
              {summary?.running_counter != null ? ` · counter ${summary.running_counter}` : ""}
              {stageActive > 0 || (summary?.dsl_executions_active ?? 0) > 0
                ? ` · ${stageActive} stage · ${summary?.dsl_executions_active ?? 0} DSL`
                : ""}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Clock className="h-4 w-4 text-amber-400" />
              Queued
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold" data-testid="queued-execution-count">
              {fleet.isLoading ? "…" : (summary?.queued ?? 0)}
            </p>
            {(stageQueued > 0 || (summary?.dsl_executions_queued ?? 0) > 0) && (
              <p className="text-xs text-muted-foreground mt-1">
                {stageQueued} stage · {summary?.dsl_executions_queued ?? 0} DSL
              </p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-red-400" />
              Failed
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">{fleet.isLoading ? "…" : (summary?.failed ?? 0)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Users className="h-4 w-4 text-emerald-400" />
              Workers
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">{fleet.isLoading ? "…" : (summary?.workers ?? 0)}</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Activity className="h-4 w-4" />
              24h throughput
            </CardTitle>
          </CardHeader>
          <CardContent>
            {metrics.isLoading ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : (
              <dl className="grid grid-cols-3 gap-4 text-center">
                <div>
                  <dt className="text-xs text-muted-foreground">Submitted</dt>
                  <dd className="text-2xl font-semibold">{throughput?.submitted ?? 0}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">Succeeded</dt>
                  <dd className="text-2xl font-semibold text-emerald-400">{throughput?.succeeded ?? 0}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">Failed</dt>
                  <dd className="text-2xl font-semibold text-red-400">{throughput?.failed ?? 0}</dd>
                </div>
              </dl>
            )}
            <p className="text-sm text-muted-foreground mt-4" data-testid="tool-dispatch-p95">
              Tool dispatch p95:{" "}
              {p95 != null ? `${p95.toFixed(1)} ms` : metrics.isLoading ? "…" : "n/a"}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between gap-2">
              <CardTitle className="text-base flex items-center gap-2">
                <Server className="h-4 w-4" />
                Worker health
              </CardTitle>
              <WorkerHealthCardLink />
            </div>
          </CardHeader>
          <CardContent>
            <WorkerHealthList
              workers={workers.data?.workers ?? []}
              loading={workers.isLoading}
            />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between gap-2">
            <CardTitle className="text-base">Recent runs</CardTitle>
            <Link to="/executions" className="text-sm text-primary hover:underline">
              View all
            </Link>
          </div>
        </CardHeader>
        <CardContent>
          {recentRuns.isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : recent.length === 0 ? (
            <EmptyState
              title="No runs yet"
              description="Start a stage job from Journeys or submit a DSL execution."
              action={
                <Link to="/journeys" className="text-sm text-primary hover:underline">
                  Open journeys
                </Link>
              }
            />
          ) : (
            <ul className="divide-y divide-border">
              {recent.map((run) => (
                <li key={`${run.kind}-${run.id}`} className="py-2 flex items-center justify-between gap-2">
                  <Link
                    to={
                      run.kind === "stage_job"
                        ? `/executions/stage/${run.journeyId}/${run.id}`
                        : `/executions/${run.id}`
                    }
                    className="text-sm text-primary hover:underline font-mono"
                  >
                    {truncateId(run.id, 14)}
                  </Link>
                  <span className="text-sm text-muted-foreground truncate">
                    {run.kind === "stage_job" ? run.journeyName ?? run.journeyId : run.journeyId}
                  </span>
                  <StatusBadge status={run.status} />
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">DSL executions running</CardTitle>
        </CardHeader>
        <CardContent>
          {running.isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : (running.data?.length ?? 0) === 0 ? (
            <EmptyState title="No active DSL executions" description="DSL runs appear here when submitted from the YAML studio." />
          ) : (
            <ul className="divide-y divide-border">
              {running.data!.map((ex) => (
                <li key={ex.execution_id} className="py-2 flex items-center justify-between gap-2">
                  <Link to={`/executions/${ex.execution_id}`} className="text-sm text-primary hover:underline">
                    {truncateId(ex.execution_id)}
                  </Link>
                  <span className="text-sm text-muted-foreground">{ex.journey_id}</span>
                  <StatusBadge status={ex.status} />
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
