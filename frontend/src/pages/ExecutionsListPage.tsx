import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { EmptyState } from "@/components/EmptyState";
import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/services/api";
import { truncateId } from "@/lib/utils";
import type { UnifiedRunRow } from "@/types/stageJourney";

function runHref(row: UnifiedRunRow): string {
  if (row.kind === "stage_job") {
    return `/executions/stage/${row.journeyId}/${row.id}`;
  }
  return `/executions/${row.id}`;
}

function runLabel(row: UnifiedRunRow): string {
  return row.kind === "stage_job" ? row.id : truncateId(row.id, 12);
}

export function ExecutionsListPage() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["runs"],
    queryFn: () => api.listAllRuns(),
    refetchInterval: 5_000,
  });

  const rows = data ?? [];
  const running = rows.filter((r) => {
    const s = r.status.toLowerCase();
    return s === "running" || s === "in_progress";
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Executions</h2>
          <p className="text-sm text-muted-foreground">
            Stage jobs and DSL runs in one monitor — auto-refreshes every 5s.
          </p>
        </div>
        <button type="button" className="text-sm text-primary hover:underline" onClick={() => refetch()}>
          Refresh
        </button>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Total runs</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-bold">{rows.length}</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Running now</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-bold text-blue-400">{running.length}</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Journeys</CardTitle>
          </CardHeader>
          <CardContent>
            <Link to="/journeys" className="text-sm text-primary hover:underline">
              Browse journeys →
            </Link>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">All runs</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : error ? (
            <EmptyState title="Failed to load" description={String(error)} />
          ) : rows.length === 0 ? (
            <EmptyState
              title="No runs yet"
              description="Open a journey, start processing on a stage, or submit a DSL execution."
              action={
                <Link to="/journeys" className="text-sm text-primary hover:underline">
                  Go to journeys
                </Link>
              }
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-muted-foreground border-b border-border">
                    <th className="py-2 pr-4">Run</th>
                    <th className="py-2 pr-4">Type</th>
                    <th className="py-2 pr-4">Journey</th>
                    <th className="py-2 pr-4">Stage</th>
                    <th className="py-2">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={`${row.kind}-${row.id}`} className="border-b border-border/50">
                      <td className="py-2 pr-4">
                        <Link to={runHref(row)} className="text-primary hover:underline font-mono">
                          {runLabel(row)}
                        </Link>
                      </td>
                      <td className="py-2 pr-4 capitalize">{row.kind === "stage_job" ? "Stage job" : "DSL"}</td>
                      <td className="py-2 pr-4">
                        {row.kind === "stage_job" && row.journeyName ? (
                          <Link to={`/journeys/${row.journeyId}`} className="hover:underline">
                            {row.journeyName}
                          </Link>
                        ) : (
                          row.journeyId
                        )}
                      </td>
                      <td className="py-2 pr-4 text-muted-foreground">
                        {row.kind === "stage_job" ? row.stageId ?? "—" : "—"}
                      </td>
                      <td className="py-2">
                        <StatusBadge status={row.status} />
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
