import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { Icon } from "@/components/ds/Icon";
import { PageHeader, Panel, StatusPill } from "@/components/ds/kit";
import { ExecutionGraphView } from "@/components/execution/ExecutionGraphView";
import { Button } from "@/components/ui/button";
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
  const journeyId = execution.data?.journey_id ? String(execution.data.journey_id) : null;
  const nodeStates = nodes.data ?? [];
  const doneNodes = nodeStates.filter((n) => ["succeeded", "completed"].includes(n.status.toLowerCase())).length;
  const shown = events.slice().reverse().slice(0, 30);

  return (
    <div className="space-y-5">
      <PageHeader
        back={
          <Link to="/executions" className="inline-flex items-center gap-1 text-muted-foreground transition-colors hover:text-foreground">
            <Icon name="chevron-left" className="h-3.5 w-3.5" />
            Executions
          </Link>
        }
        title={<span className="font-mono text-lg" title={executionId}>{truncateId(executionId, 16)}</span>}
        description={journeyId ? <>DSL execution of <span className="font-mono text-foreground">{journeyId}</span></> : "DSL execution"}
        meta={
          <>
            <StatusPill status={status} variant="soft" />
            <StatusPill tone={connected ? "success" : "warning"} live={connected} data-testid="sse-status" className="font-normal text-muted-foreground">
              SSE {connected ? "connected" : "connecting…"}
            </StatusPill>
          </>
        }
        actions={
          !["succeeded", "failed", "cancelled"].includes(status.toLowerCase()) ? (
            <Button variant="destructive" size="sm" onClick={() => cancelMut.mutate()} disabled={cancelMut.isPending}>
              <Icon name="close" className="h-3 w-3" />
              Cancel
            </Button>
          ) : null
        }
      />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_400px]">
        <Panel
          title="Live graph"
          description={nodeStates.length > 0 ? `${doneNodes} of ${nodeStates.length} nodes finished` : undefined}
          bodyClassName="p-3 sm:p-3"
        >
          <ExecutionGraphView graph={graph.data} nodeStates={nodeStates} />
        </Panel>

        <Panel title="Event stream" description={events.length > 0 ? `Latest ${shown.length} of ${events.length}` : undefined} flush>
          <ul className="scroll-thin max-h-[444px] divide-y divide-border overflow-y-auto" data-testid="event-stream">
            {events.length === 0 ? (
              <li className="px-4 py-8 text-center text-sm text-subtle-foreground sm:px-5">Waiting for events…</li>
            ) : (
              shown.map((ev, i) => (
                <li key={`${ev.timestamp}-${i}`} className="px-4 py-2 sm:px-5">
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="font-mono text-xs font-medium text-primary dark:text-brand-hi">{ev.type}</span>
                    {ev.timestamp ? (
                      <span className="num shrink-0 text-xs text-subtle-foreground">
                        {new Date(ev.timestamp).toLocaleTimeString(undefined, { hour12: false })}
                      </span>
                    ) : null}
                  </div>
                  <div className="mt-0.5 break-all font-mono text-xs leading-5 text-muted-foreground">{JSON.stringify(ev.data ?? {})}</div>
                </li>
              ))
            )}
          </ul>
        </Panel>
      </div>
    </div>
  );
}
