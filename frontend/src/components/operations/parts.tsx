/**
 * Shared presentational pieces for the Operations area. No data fetching here.
 */
import type { ReactNode } from "react";

import { Icon } from "@/components/ds/Icon";
import { EmptyState, InlineError, Skeleton, StatusPill, toneOf, type Tone } from "@/components/ds/kit";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** Title block of one Operations section (the page title is the h2 above it). */
export function SectionHeader({
  title,
  description,
  meta,
  actions,
}: {
  title: ReactNode;
  description?: ReactNode;
  meta?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <h3 className="text-lg font-medium tracking-tight text-foreground">{title}</h3>
          {meta}
        </div>
        {description ? <p className="mt-1 max-w-3xl text-sm text-muted-foreground">{description}</p> : null}
      </div>
      {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}

/** Outline button with the refresh icon; the icon spins while `spinning`. */
export function RefreshButton({
  onClick,
  disabled,
  spinning,
  children,
}: {
  onClick: () => void;
  disabled?: boolean;
  spinning?: boolean;
  children: ReactNode;
}) {
  return (
    <Button variant="outline" size="sm" onClick={onClick} disabled={disabled}>
      <Icon name="refresh" className={spinning ? "animate-spin" : undefined} />
      {children}
    </Button>
  );
}

/** Tone for SLA / health words. "unknown" stays neutral instead of amber. */
export function healthTone(status?: string | null): Tone {
  if (!status || status === "unknown") return "neutral";
  return toneOf(status);
}

/** connected / disconnected / checking pill used in data-store headers. */
export function ConnectionPill({ loading, connected }: { loading: boolean; connected?: boolean }) {
  return (
    <StatusPill variant="soft" tone={loading ? "neutral" : connected ? "success" : "danger"}>
      {loading ? "checking" : connected ? "connected" : "disconnected"}
    </StatusPill>
  );
}

export type StripColumns = 2 | 3 | 4 | 5 | 6;

/** Column count for a MetricStrip with `n` items. */
export function stripColumns(n: number): StripColumns {
  if (n <= 2) return 2;
  if (n >= 6) return 6;
  return n as StripColumns;
}

const STRIP_COLS: Record<StripColumns, string> = {
  2: "lg:grid-cols-2",
  3: "lg:grid-cols-3",
  4: "lg:grid-cols-4",
  5: "sm:grid-cols-3 lg:grid-cols-5",
  6: "sm:grid-cols-3 xl:grid-cols-6",
};

/** Loading placeholder with the same shape as a MetricStrip. */
export function MetricStripSkeleton({ count, className }: { count: StripColumns; className?: string }) {
  return (
    <div
      aria-busy="true"
      aria-label="Loading"
      className={cn("grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-border bg-border shadow-xs", STRIP_COLS[count], className)}
    >
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="bg-card p-4 sm:px-5">
          <Skeleton className="h-4 w-20" />
          <Skeleton className="mt-2.5 h-7 w-16" />
        </div>
      ))}
    </div>
  );
}

/** Class for a MetricStrip that sits flush inside a `<Panel flush>`. */
export const FLUSH_STRIP = "rounded-none border-0 shadow-none";

/** Loading / error / empty wrapper for a chart area of a fixed height. */
export function ChartBody({
  loading,
  error,
  empty,
  height = 240,
  children,
}: {
  loading?: boolean;
  error?: string | null;
  /** Message to show instead of the chart when there is nothing to plot. */
  empty?: string | null | false;
  height?: number;
  children: ReactNode;
}) {
  if (loading) return <Skeleton className="w-full" style={{ height }} />;
  if (error) {
    return (
      <div className="flex items-center" style={{ minHeight: height }}>
        <InlineError className="w-full">{error}</InlineError>
      </div>
    );
  }
  if (empty) {
    return (
      <div className="flex items-center justify-center" style={{ minHeight: height }}>
        <EmptyState bare icon="chart-bar" title={empty} className="py-0" />
      </div>
    );
  }
  return <>{children}</>;
}
