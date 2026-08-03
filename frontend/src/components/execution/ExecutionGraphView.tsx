import { useMemo } from "react";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import type { ExecutionGraph, ExecutionNodeState } from "@/types/api";

const NODE_COLORS: Record<string, string> = {
  pending: "#64748b",
  PENDING: "#64748b",
  running: "#3b82f6",
  RUNNING: "#3b82f6",
  succeeded: "#22c55e",
  SUCCEEDED: "#22c55e",
  failed: "#ef4444",
  FAILED: "#ef4444",
  skipped: "#94a3b8",
  SKIPPED: "#94a3b8",
};

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
        border: `2px solid ${NODE_COLORS[status] ?? NODE_COLORS.pending}`,
        borderRadius: 8,
        padding: 8,
        fontSize: 12,
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
        <p className="text-sm text-muted-foreground">Graph not available yet.</p>
      </div>
    );
  }

  return (
    <div className={className} style={{ height: 360 }} aria-label="Execution graph">
      <ReactFlow nodes={nodes} edges={edges} fitView nodesDraggable={false} nodesConnectable={false}>
        <Background />
        <Controls showInteractive={false} />
        <MiniMap pannable zoomable />
      </ReactFlow>
    </div>
  );
}
