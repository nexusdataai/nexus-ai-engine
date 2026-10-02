import { Link } from "react-router-dom";

import { cn } from "@/lib/utils";
import type { FleetWorker } from "@/types/api";

type Props = {
  workers: FleetWorker[];
  loading?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
};

const HEALTH: Record<string, { label: string; className: string }> = {
  healthy: {
    label: "Healthy",
    className: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  },
  idle: {
    label: "Idle",
    className: "bg-muted text-muted-foreground border-border",
  },
  stale: {
    label: "Stale",
    className: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  },
  offline: {
    label: "Offline",
    className: "bg-red-500/15 text-red-300 border-red-500/30",
  },
};

function healthKey(status: string): keyof typeof HEALTH {
  const key = (status || "").toLowerCase();
  if (key === "healthy" || key === "running") return "healthy";
  if (key === "idle") return "idle";
  if (key === "stale") return "stale";
  if (key === "offline" || key === "failed") return "offline";
  return "idle";
}

export function WorkerHealthList({
  workers,
  loading,
  emptyTitle = "No workers",
  emptyDescription = "Worker registry is empty.",
}: Props) {
  if (loading) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }
  if (workers.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        {emptyTitle} — {emptyDescription}
      </p>
    );
  }
  return (
    <ul className="divide-y divide-border">
      {workers.map((w) => {
        const health = HEALTH[healthKey(w.status)];
        return (
          <li key={`${w.worker_id}-${w.role}`} className="py-2 flex items-center justify-between gap-2">
            <span className="text-sm font-mono truncate">{w.worker_id}</span>
            <span className="text-xs text-muted-foreground">{w.role}</span>
            <span
              className={cn(
                "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium",
                health.className,
              )}
            >
              {health.label}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

export function WorkerHealthCardLink() {
  return (
    <Link to="/workers" className="text-sm text-primary hover:underline">
      Manage workers
    </Link>
  );
}
