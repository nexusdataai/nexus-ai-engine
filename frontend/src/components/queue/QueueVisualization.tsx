import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { cn, truncateId } from "@/lib/utils";
import type { QueueJob } from "@/types/api";

type Props = {
  jobs: QueueJob[];
  maxGlobal: number;
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
        "inline-flex shrink-0 items-center gap-1 rounded-md border px-2 py-1 text-xs font-mono transition-all duration-500",
        job.leaving && "opacity-0 scale-75 max-w-0 px-0 border-transparent overflow-hidden",
        job.state === "waiting" && "border-amber-500/40 bg-amber-500/10 text-amber-200",
        job.state === "claimed" && "border-slate-500/40 bg-slate-500/10 text-slate-200",
        job.state === "running" && "border-blue-500/40 bg-blue-500/10 text-blue-200",
        className,
      )}
      title={job.job_id}
    >
      <span>{truncateId(job.job_id, 10)}</span>
    </Link>
  );
}

export function QueueVisualization({ jobs, maxGlobal }: Props) {
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
  }, [jobs]);

  const { waiting, running, claimed } = useMemo(() => {
    const w = displayJobs.filter((j) => j.state === "waiting" && !j.leaving);
    const r = displayJobs.filter((j) => j.state === "running" && !j.leaving);
    const c = displayJobs.filter((j) => j.state === "claimed" && !j.leaving);
    return { waiting: w, running: r, claimed: c };
  }, [displayJobs]);

  const slots = Array.from({ length: maxGlobal }, (_, i) => running[i] ?? claimed[i - running.length] ?? null);

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-border bg-muted/20 p-4">
        <p className="text-xs font-medium text-muted-foreground mb-2">Waiting lane</p>
        <div
          className="flex min-h-10 flex-wrap items-center gap-2 transition-all duration-500"
          data-testid="queue-waiting-lane"
        >
          {waiting.length === 0 ? (
            <span className="text-xs text-muted-foreground italic">No jobs waiting</span>
          ) : (
            waiting.map((job) => <JobChip key={job.stream_id} job={job} />)
          )}
        </div>
      </div>

      <div className="flex items-center justify-center text-muted-foreground">
        <span className="text-lg">→</span>
      </div>

      <div className="rounded-lg border border-border bg-muted/20 p-4">
        <p className="text-xs font-medium text-muted-foreground mb-2">
          Active slots ({running.length} running / {maxGlobal} max)
        </p>
        <div
          className={cn(
            "grid gap-2",
            maxGlobal > 10 ? "sm:grid-cols-5 lg:grid-cols-10" : "sm:grid-cols-2 lg:grid-cols-5",
          )}
          data-testid="queue-active-slots"
        >
          {slots.map((job, idx) => (
            <div
              key={job?.stream_id ?? `empty-${idx}`}
              className={cn(
                "flex min-h-12 items-center justify-center rounded-md border border-dashed px-2 transition-all duration-500",
                job ? "border-solid" : "border-border/60 bg-background/40",
              )}
            >
              {job ? (
                <JobChip job={job} className="w-full justify-center" />
              ) : (
                <span className="text-xs text-muted-foreground">empty</span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
