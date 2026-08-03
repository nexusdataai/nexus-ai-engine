import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { EmptyState } from "@/components/EmptyState";
import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/services/api";
import { truncateId } from "@/lib/utils";

export function ExecutionsListPage() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["executions"],
    queryFn: () => api.listExecutions(),
    refetchInterval: 5_000,
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Executions monitor</h2>
          <p className="text-sm text-muted-foreground">Auto-refreshes every 5s</p>
        </div>
        <button
          type="button"
          className="text-sm text-primary hover:underline"
          onClick={() => refetch()}
        >
          Refresh
        </button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">All executions</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : error ? (
            <EmptyState title="Failed to load" description={String(error)} />
          ) : !data?.length ? (
            <EmptyState title="No executions" description="Run a journey to create one." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-muted-foreground border-b border-border">
                    <th className="py-2 pr-4">Execution</th>
                    <th className="py-2 pr-4">Journey</th>
                    <th className="py-2">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((ex) => (
                    <tr key={ex.execution_id} className="border-b border-border/50">
                      <td className="py-2 pr-4">
                        <Link
                          to={`/executions/${ex.execution_id}`}
                          className="text-primary hover:underline font-mono"
                        >
                          {truncateId(ex.execution_id, 12)}
                        </Link>
                      </td>
                      <td className="py-2 pr-4">{ex.journey_id}</td>
                      <td className="py-2">
                        <StatusBadge status={ex.status} />
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
