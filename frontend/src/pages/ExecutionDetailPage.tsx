import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { ExecutionGraphView } from "@/components/execution/ExecutionGraphView";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useExecutionStream } from "@/hooks/useExecutionStream";
import { api } from "@/services/api";
import { truncateId } from "@/lib/utils";

export function ExecutionDetailPage() {
  const { executionId = "" } = useParams();
  const qc = useQueryClient();
  const { events, connected } = useExecutionStream(executionId);

  const execution = useQuery({
    queryKey: ["execution", executionId],
    queryFn: () => api.getExecution(executionId),
    refetchInterval: 3_000,
    enabled: Boolean(executionId),
  });

  const nodes = useQuery({
    queryKey: ["execution-nodes", executionId],
    queryFn: () => api.listExecutionNodes(executionId),
    refetchInterval: 3_000,
    enabled: Boolean(executionId),
  });

  const graph = useQuery({
    queryKey: ["execution-graph", executionId],
    queryFn: () => api.getExecutionGraph(executionId),
    refetchInterval: 5_000,
    enabled: Boolean(executionId),
  });

  const cancelMut = useMutation({
    mutationFn: () => api.cancelExecution(executionId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["execution", executionId] });
    },
  });

  const status = String(execution.data?.status ?? "unknown");

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="outline" size="sm" asChild>
          <Link to="/executions">← Executions</Link>
        </Button>
        <h2 className="text-lg font-semibold font-mono">{truncateId(executionId, 16)}</h2>
        <StatusBadge status={status} />
        <span
          className={`text-xs ${connected ? "text-emerald-400" : "text-muted-foreground"}`}
          data-testid="sse-status"
        >
          SSE {connected ? "connected" : "connecting…"}
        </span>
        {!["succeeded", "failed", "cancelled"].includes(status.toLowerCase()) ? (
          <Button
            variant="destructive"
            size="sm"
            onClick={() => cancelMut.mutate()}
            disabled={cancelMut.isPending}
          >
            Cancel
          </Button>
        ) : null}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Live graph</CardTitle>
        </CardHeader>
        <CardContent>
          <ExecutionGraphView graph={graph.data} nodeStates={nodes.data ?? []} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Event stream</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="max-h-48 overflow-y-auto font-mono text-xs space-y-1" data-testid="event-stream">
            {events.length === 0 ? (
              <li className="text-muted-foreground">Waiting for events…</li>
            ) : (
              events
                .slice()
                .reverse()
                .slice(0, 30)
                .map((ev, i) => (
                  <li key={`${ev.timestamp}-${i}`}>
                    <span className="text-primary">{ev.type}</span>{" "}
                    {JSON.stringify(ev.data ?? {})}
                  </li>
                ))
            )}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
