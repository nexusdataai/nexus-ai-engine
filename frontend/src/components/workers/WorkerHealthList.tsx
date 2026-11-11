import { Link } from "react-router-dom";

import { SkeletonRows, StatusPill, type Tone } from "@/components/ds/kit";
import { relativeTime } from "@/utils/time";
import type { FleetWorker } from "@/types/api";

type Props = {
  workers: FleetWorker[];
  loading?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
};

const HEALTH: Record<string, { label: string; tone: Tone }> = {
  healthy: { label: "Healthy", tone: "success" },
  idle: { label: "Idle", tone: "neutral" },
  stale: { label: "Stale", tone: "warning" },
  offline: { label: "Offline", tone: "danger" },
};

function healthKey(status: string): keyof typeof HEALTH {
  const key = (status || "").toLowerCase();
  if (key === "healthy" || key === "running") return "healthy";
  if (key === "idle") return "idle";
  if (key === "stale") return "stale";
  if (key === "offline" || key === "failed") return "offline";
  return "idle";
}

/** Pod names share a long deployment prefix; show the part that differs. */
export function shortWorkerName(id: string): string {
  const parts = id.split("-");
  return parts.length > 2 ? parts.slice(-2).join("-") : id;
}

export function WorkerHealthList({
  workers,
  loading,
  emptyTitle = "No workers",
  emptyDescription = "Worker registry is empty.",
}: Props) {
  if (loading) {
    return <SkeletonRows rows={3} />;
  }
  if (workers.length === 0) {
    return (
      <p className="px-4 py-6 text-sm text-muted-foreground sm:px-5">
        {emptyTitle} — {emptyDescription}
      </p>
    );
  }
  return (
    <ul className="divide-y divide-border">
      {workers.map((w) => {
        const health = HEALTH[healthKey(w.status)];
        return (
          <li key={`${w.worker_id}-${w.role}`} className="flex items-center justify-between gap-3 px-4 py-2.5 sm:px-5">
            <div className="min-w-0">
              <div className="truncate font-mono text-sm text-foreground" title={w.worker_id}>
                {shortWorkerName(w.worker_id)}
              </div>
              <div className="truncate text-xs text-muted-foreground">
                {w.role} · seen {relativeTime(w.last_seen)}
              </div>
            </div>
            <StatusPill tone={health.tone}>{health.label}</StatusPill>
          </li>
        );
      })}
    </ul>
  );
}

export function WorkerHealthCardLink() {
  return (
    <Link to="/workers" className="link text-sm">
      Manage workers
    </Link>
  );
}
