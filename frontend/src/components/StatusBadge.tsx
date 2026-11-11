import { StatusPill } from "@/components/ds/kit";

/** Status of a run, job, worker or schedule: a dot and a word. */
export function StatusBadge({ status, className }: { status: string; className?: string }) {
  return <StatusPill status={status} className={className} />;
}
