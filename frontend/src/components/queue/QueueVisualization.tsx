import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { cn, truncateId } from "@/lib/utils";
import type { QueueJob } from "@/types/api";

type Props = {
  jobs: QueueJob[];
  maxGlobal: number;
  /** Redis active counter when job rows lag behind summary */
  activeFromSummary?: number;
};

type AnimatedJob = QueueJob & { leaving?: boolean };

function jobHref(job: QueueJob): string {
  if (job.job_kind === "dsl_execution") {
    return `/executions/${job.job_id}`;
  }
  return `/executions/stage/${job.journey_id}/${job.job_id}`;
}

function JobChip({ job, className }: { job: AnimatedJob; className?: string }) {
  return (
    <Link
      to={jobHref(job)}
      className={cn(
        "inline-flex h-7 shrink-0 items-center gap-1.5 rounded-md border px-2 font-mono text-xs transition-all duration-500",
        job.leaving && "max-w-0 scale-75 overflow-hidden border-transparent px-0 opacity-0",
        job.state === "waiting" && "border-warning/30 bg-warning/10 text-warning",
        job.state === "claimed" && "border-border-strong bg-surface-2 text-muted-foreground",
        job.state === "running" && "border-brand/40 bg-brand/10 text-primary dark:text-brand-hi",
        className,
      )}
      title={job.job_id}
    >
      <span className="truncate">{truncateId(job.job_id, 10)}</span>
    </Link>
  );
}

/**
 * The queue as it is right now: jobs wait on the left and move into one of
 * the engine's running slots on the right. One slot per unit of the global
 * job limit.
 */
export function QueueVisualization({ jobs, maxGlobal, activeFromSummary }: Props) {
  const [displayJobs, setDisplayJobs] = useState<AnimatedJob[]>(jobs);
  const prevIds = useRef<Set<string>>(new Set());

  useEffect(() => {
    const nextIds = new Set(jobs.map((j) => j.stream_id));
    const leaving = displayJobs
      .filter((j) => !nextIds.has(j.stream_id) && !j.leaving)
      .map((j) => ({ ...j, leaving: true }));

    if (leaving.length > 0) {
      setDisplayJobs((prev) => {
        const merged = [...prev.filter((j) => nextIds.has(j.stream_id) || j.leaving), ...leaving];
        return merged;
      });
      const timer = window.setTimeout(() => {
        setDisplayJobs(jobs);
      }, 450);
      prevIds.current = nextIds;
      return () => window.clearTimeout(timer);
    }

    setDisplayJobs(jobs);
    prevIds.current = nextIds;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobs]);

  const { waiting, running } = useMemo(() => {
    const r = displayJobs.filter((j) => j.state === "running" && !j.leaving);
    // Claimed = delivered to a worker but not executing yet (at global capacity).
    const w = displayJobs.filter(
      (j) => (j.state === "waiting" || j.state === "claimed") && !j.leaving,
    );
    return { waiting: w, running: r };
  }, [displayJobs]);

  const activeSlots = Math.max(running.length, activeFromSummary ?? 0, 0);
  const slots = Array.from({ length: maxGlobal }, (_, i) => {
    if (i < running.length) return running[i];
    if (i < activeSlots) {
      return {
        stream_id: `active-placeholder-${i}`,
        job_id: "…",
        journey_id: "",
        job_kind: "active",
        state: "running" as const,
        consumer_name: "",
        idle_ms: 0,
        leaving: false,
      } satisfies AnimatedJob;
    }
    return null;
  });
  const moving = waiting.length > 0 || activeSlots > 0;

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(220px,0.9fr)_56px_minmax(0,2.4fr)] lg:gap-0">
      <div>
        <div className="mb-2 flex items-baseline justify-between gap-2">
          <p className="text-sm font-medium text-foreground">Waiting</p>
          <span className="num text-xs text-muted-foreground">{waiting.length} in line</span>
        </div>
        <div
          className="flex min-h-[120px] flex-wrap content-start items-start gap-1.5 rounded-lg border border-border bg-surface-2/50 p-3 transition-all duration-500"
          data-testid="queue-waiting-lane"
        >
          {waiting.length === 0 ? (
            <span className="m-auto text-sm text-subtle-foreground">No jobs waiting</span>
          ) : (
            waiting.map((job) => <JobChip key={job.stream_id} job={job} />)
          )}
        </div>
      </div>

      <div className="hidden items-center justify-center lg:flex" aria-hidden="true">
        <svg viewBox="0 0 56 12" className="mt-7 h-3 w-full">
          <line x1="6" y1="6" x2="46" y2="6" strokeWidth="1.5" strokeLinecap="round" className={cn(moving ? "flow-line stroke-brand" : "stroke-border-strong")} strokeDasharray={moving ? undefined : "2 6"} />
          <path d="M44 2 l4 4 l-4 4" fill="none" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className={moving ? "stroke-brand" : "stroke-border-strong"} />
        </svg>
      </div>

      <div className="min-w-0">
        <div className="mb-2 flex items-baseline justify-between gap-2">
          <p className="text-sm font-medium text-foreground">
            Active slots <span className="font-normal text-muted-foreground">({activeSlots} running / {maxGlobal} max)</span>
          </p>
          <span className="num text-xs text-muted-foreground">{Math.max(maxGlobal - activeSlots, 0)} free</span>
        </div>
        <div
          className={cn(
            "grid gap-1.5 rounded-lg border border-border bg-surface-2/50 p-3",
            maxGlobal > 10 ? "grid-cols-5 lg:grid-cols-10" : "grid-cols-2 sm:grid-cols-5",
          )}
          data-testid="queue-active-slots"
        >
          {slots.map((job, idx) => (
            <div
              key={job?.stream_id ?? `empty-${idx}`}
              title={job ? undefined : "empty"}
              className={cn(
                "flex h-9 min-w-0 items-center justify-center rounded-md border transition-all duration-500",
                job ? "border-transparent" : "border-dashed border-border-strong/70",
              )}
            >
              {job && !job.stream_id.startsWith("active-placeholder-") ? (
                <JobChip job={job} className="h-full w-full justify-center" />
              ) : job ? (
                <span className="flex h-full w-full items-center justify-center rounded-md border border-brand/40 bg-brand/10 font-mono text-xs text-primary dark:text-brand-hi">
                  running
                </span>
              ) : (
                <span className="sr-only">empty</span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
