import { cn } from "@/lib/utils";

const STATUS_STYLES: Record<string, string> = {
  running: "bg-blue-500/15 text-blue-300 border-blue-500/30",
  RUNNING: "bg-blue-500/15 text-blue-300 border-blue-500/30",
  succeeded: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  SUCCEEDED: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  failed: "bg-red-500/15 text-red-300 border-red-500/30",
  FAILED: "bg-red-500/15 text-red-300 border-red-500/30",
  pending: "bg-muted text-muted-foreground border-border",
  PENDING: "bg-muted text-muted-foreground border-border",
  cancelled: "bg-orange-500/15 text-orange-300 border-orange-500/30",
  CANCELLED: "bg-orange-500/15 text-orange-300 border-orange-500/30",
  paused: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  PAUSED: "bg-amber-500/15 text-amber-300 border-amber-500/30",
};

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  const key = status.toUpperCase();
  const style = STATUS_STYLES[status] ?? STATUS_STYLES[key] ?? STATUS_STYLES.pending;
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium capitalize",
        style,
        className,
      )}
    >
      {status.replace(/_/g, " ").toLowerCase()}
    </span>
  );
}
