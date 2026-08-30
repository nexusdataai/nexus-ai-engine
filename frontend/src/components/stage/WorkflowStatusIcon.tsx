import { Check, Circle, Loader2, Minus, X } from "lucide-react";

import { cn } from "@/lib/utils";
import type { StepStatus } from "@/types/stageJobStream";

type Props = {
  status: StepStatus | string;
  className?: string;
};

export function WorkflowStatusIcon({ status, className }: Props) {
  const s = String(status).toLowerCase();

  if (s === "running" || s === "in_progress" || s === "queued") {
    return <Loader2 className={cn("h-4 w-4 shrink-0 text-blue-400 animate-spin", className)} aria-hidden />;
  }
  if (s === "completed" || s === "success" || s === "succeeded") {
    return (
      <span
        className={cn(
          "inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-400",
          className,
        )}
        aria-hidden
      >
        <Check className="h-3 w-3" strokeWidth={3} />
      </span>
    );
  }
  if (s === "failed" || s === "error") {
    return (
      <span
        className={cn(
          "inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-red-500/20 text-red-400",
          className,
        )}
        aria-hidden
      >
        <X className="h-3 w-3" strokeWidth={3} />
      </span>
    );
  }
  if (s === "cancelled") {
    return <Minus className={cn("h-4 w-4 shrink-0 text-amber-400", className)} aria-hidden />;
  }

  return <Circle className={cn("h-4 w-4 shrink-0 text-muted-foreground/50", className)} aria-hidden />;
}
