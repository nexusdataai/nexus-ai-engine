import { useMemo } from "react";
import {
  Controls,
  MiniMap,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import type { ExecutionGraph, ExecutionNodeState } from "@/types/api";

const TOKEN: Record<string, string> = {
  pending: "hsl(var(--border-strong))",
  running: "hsl(var(--brand))",
  succeeded: "hsl(var(--success))",
  completed: "hsl(var(--success))",
  failed: "hsl(var(--destructive))",
  skipped: "hsl(var(--border-strong))",
  cancelled: "hsl(var(--warning))",
};
const nodeColor = (status: string) => TOKEN[String(status).toLowerCase()] ?? TOKEN.pending;

function layoutNodes(
  graph: ExecutionGraph,
  nodeStates: ExecutionNodeState[],
): { nodes: Node[]; edges: Edge[] } {
  const statusById = new Map(nodeStates.map((n) => [n.node_id, n.status]));
  const index = new Map(graph.nodes.map((n, i) => [n.node_id, i]));

  const nodes: Node[] = graph.nodes.map((n, i) => {
    const status = statusById.get(n.node_id) ?? "pending";
    const col = i % 3;
    const row = Math.floor(i / 3);
    return {
      id: n.node_id,
      data: {
        label: n.display_name || n.tool_id || n.kind,
        status,
      },
      position: { x: col * 220, y: row * 100 },
      style: {
        border: `1.5px solid ${nodeColor(status)}`,
        borderRadius: 10,
        padding: "8px 12px",
        fontSize: 13,
        fontFamily: "var(--font-sans)",
        boxShadow: "var(--shadow-xs)",
        background: "hsl(var(--card))",
        color: "hsl(var(--foreground))",
        minWidth: 140,
      },
    };
  });

  const edges: Edge[] = graph.edges.map((e, i) => ({
    id: `e-${i}`,
    source: e.from_node,
    target: e.to_node,
    animated: statusById.get(e.to_node)?.toUpperCase() === "RUNNING",
  }));

  // Fallback edges from depends_on when graph.edges empty
  if (edges.length === 0) {
    graph.nodes.forEach((n) => {
      (n.depends_on ?? []).forEach((dep, j) => {
        edges.push({
          id: `dep-${n.node_id}-${j}`,
          source: dep,
          target: n.node_id,
        });
      });
    });
  }

  void index;
  return { nodes, edges };
}

export function ExecutionGraphView({
  graph,
  nodeStates,
  className,
}: {
  graph: ExecutionGraph | undefined;
  nodeStates: ExecutionNodeState[];
  className?: string;
}) {
  const { nodes, edges } = useMemo(() => {
    if (!graph) return { nodes: [], edges: [] };
    return layoutNodes(graph, nodeStates);
  }, [graph, nodeStates]);

  if (!graph) {
    return (
      <div className={className}>
        <p className="py-10 text-center text-sm text-muted-foreground">Graph not available yet.</p>
      </div>
    );
  }

  return (
    <div className={`canvas-dots overflow-hidden rounded-lg border border-border ${className ?? ""}`} style={{ height: 420 }} aria-label="Execution graph">
      <ReactFlow nodes={nodes} edges={edges} fitView nodesDraggable={false} nodesConnectable={false}>
        <Controls showInteractive={false} />
        <MiniMap pannable zoomable />
      </ReactFlow>
    </div>
  );
}
