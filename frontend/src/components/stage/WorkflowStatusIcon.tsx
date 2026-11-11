import { Icon } from "@/components/ds/Icon";
import { cn } from "@/lib/utils";
import type { StepStatus } from "@/types/stageJobStream";

type Props = {
  status: StepStatus | string;
  className?: string;
  /** Larger node used on the stage rail. */
  size?: "sm" | "md";
};

/** Status node for a stage or a step: ring + glyph, one meaning per colour. */
export function WorkflowStatusIcon({ status, className, size = "sm" }: Props) {
  const s = String(status).toLowerCase();
  const box = size === "md" ? "h-6 w-6" : "h-[18px] w-[18px]";
  const glyph = size === "md" ? "h-3 w-3" : "h-2.5 w-2.5";
  const base = cn("inline-flex shrink-0 items-center justify-center rounded-full border", box, className);

  if (s === "running" || s === "in_progress" || s === "queued") {
    return (
      <span className={cn(base, "border-brand/50 bg-brand/10 text-primary dark:text-brand-hi")} aria-hidden>
        <Icon name="spinner" className={cn(glyph, "animate-spin")} />
      </span>
    );
  }
  if (s === "completed" || s === "success" || s === "succeeded") {
    return (
      <span className={cn(base, "border-success/40 bg-success/10 text-success")} aria-hidden>
        <Icon name="check" className={glyph} />
      </span>
    );
  }
  if (s === "failed" || s === "error") {
    return (
      <span className={cn(base, "border-destructive/40 bg-destructive/10 text-destructive")} aria-hidden>
        <Icon name="close" className={cn(glyph, "scale-90")} />
      </span>
    );
  }
  if (s === "cancelled") {
    return (
      <span className={cn(base, "border-warning/40 bg-warning/10 text-warning")} aria-hidden>
        <Icon name="minus" className={glyph} />
      </span>
    );
  }

  return <span className={cn(base, "border-border-strong bg-card")} aria-hidden />;
}
