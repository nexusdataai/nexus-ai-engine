import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { Icon, type IconName } from "@/components/ds/Icon";
import { Meter } from "@/components/ds/kit";
import { cn } from "@/lib/utils";

/**
 * The engine at a glance: work moves left to right from journeys, through
 * the queue, onto workers, and out as results. Connectors animate while
 * something is actually moving through that hop.
 */

type Station = {
  to: string;
  icon: IconName;
  label: string;
  value: ReactNode;
  caption: ReactNode;
  extra?: ReactNode;
  /** Highlight: work is happening here right now. */
  live?: boolean;
};

function Connector({ active }: { active: boolean }) {
  return (
    <div className="relative hidden h-px min-w-6 flex-1 self-center lg:block" aria-hidden="true">
      <svg className="absolute inset-x-0 -top-[5px] h-[11px] w-full overflow-visible" preserveAspectRatio="none">
        <line
          x1="0" y1="5.5" x2="100%" y2="5.5"
          strokeWidth="1.5"
          className={cn(active ? "flow-line stroke-brand" : "stroke-border-strong")}
          strokeDasharray={active ? undefined : "2 6"}
          strokeLinecap="round"
        />
      </svg>
      <span className={cn("absolute -right-0.5 -top-[3px] h-[7px] w-[7px] rotate-45 border-r-[1.5px] border-t-[1.5px]", active ? "border-brand" : "border-border-strong")} />
    </div>
  );
}

function StationCard({ s }: { s: Station }) {
  return (
    <Link
      to={s.to}
      className={cn(
        "group relative flex min-w-0 flex-col rounded-xl border bg-card p-4 shadow-xs transition-[border-color,transform,box-shadow] duration-200 ease-brand hover:-translate-y-0.5 hover:shadow-md lg:w-[23%] lg:shrink-0",
        s.live ? "border-brand/50" : "border-border hover:border-brand/40",
      )}
    >
      <div className="flex items-center justify-between gap-2 text-sm text-muted-foreground">
        <span className="flex items-center gap-2">
          <Icon name={s.icon} className={cn("h-[17px] w-[17px]", s.live ? "text-primary dark:text-brand-hi" : "text-subtle-foreground")} />
          {s.label}
        </span>
        <Icon name="arrow-up-right" className="h-3.5 w-3.5 text-subtle-foreground opacity-0 transition-opacity group-hover:opacity-100" />
      </div>
      <div className="num mt-3 text-3xl font-medium tracking-tight text-foreground">{s.value}</div>
      <div className="mt-1 text-xs text-muted-foreground">{s.caption}</div>
      {s.extra ? <div className="mt-3">{s.extra}</div> : null}
    </Link>
  );
}

export type EngineFlowProps = {
  journeys: ReactNode;
  journeyJobs: ReactNode;
  queued: ReactNode;
  queuedNumber: number;
  queueHint: ReactNode;
  active: ReactNode;
  activeNumber: number;
  limit?: number;
  workersHint: ReactNode;
  succeeded: number;
  failed: number;
  resultsReady: boolean;
};

export function EngineFlow(p: EngineFlowProps) {
  const finished = p.succeeded + p.failed;
  const rate = finished > 0 ? (p.succeeded / finished) * 100 : null;
  const stations: Station[] = [
    {
      to: "/journeys",
      icon: "route",
      label: "Journeys",
      value: p.journeys,
      caption: p.journeyJobs,
    },
    {
      to: "/queue",
      icon: "layers",
      label: "Queue",
      value: p.queued,
      caption: p.queueHint,
      live: p.queuedNumber > 0,
    },
    {
      to: "/workers",
      icon: "server",
      label: "Running on workers",
      value: p.active,
      caption: p.workersHint,
      live: p.activeNumber > 0,
      extra: p.limit ? <Meter value={p.activeNumber} max={p.limit} label="Running against the global limit" /> : undefined,
    },
    {
      to: "/executions",
      icon: "check-circle",
      label: "Results, last 24 h",
      value: p.resultsReady ? (rate != null ? `${rate.toFixed(rate >= 99.95 || rate === 0 ? 0 : 1)}%` : "—") : "…",
      caption: p.resultsReady
        ? finished > 0
          ? <><span className="text-success">{p.succeeded.toLocaleString()} succeeded</span>{" · "}<span className={p.failed > 0 ? "text-destructive" : undefined}>{p.failed.toLocaleString()} failed</span></>
          : "No finished runs in this window"
        : "Counting runs…",
    },
  ];

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:flex lg:items-stretch lg:gap-0">
      {stations.map((s, i) => (
        <div key={s.label} className="contents">
          <StationCard s={s} />
          {i < stations.length - 1 ? (
            <Connector active={i === 0 ? p.queuedNumber > 0 : i === 1 ? p.activeNumber > 0 : p.activeNumber > 0} />
          ) : null}
        </div>
      ))}
    </div>
  );
}
