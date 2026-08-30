import { Link } from "react-router-dom";

import { StatusBadge } from "@/components/StatusBadge";
import type { FleetWorker } from "@/types/api";

type Props = {
  workers: FleetWorker[];
  loading?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
};

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
      {workers.map((w) => (
        <li key={`${w.worker_id}-${w.role}`} className="py-2 flex items-center justify-between gap-2">
          <span className="text-sm font-mono truncate">{w.worker_id}</span>
          <span className="text-xs text-muted-foreground">{w.role}</span>
          <StatusBadge status={w.status === "healthy" ? "SUCCEEDED" : "FAILED"} />
        </li>
      ))}
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
