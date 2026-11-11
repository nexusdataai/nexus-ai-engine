import { useCallback, useMemo, useState, useSyncExternalStore } from "react";
import { useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { Icon } from "@/components/ds/Icon";
import { Chips, EmptyState, InlineError, Notice, PageHeader, SearchInput, Segmented, SkeletonRows, StatusPill, TableShell, Toolbar, ToolbarSpacer } from "@/components/ds/kit";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { journeyListStats } from "@/lib/stageJourney";
import { api } from "@/services/api";
import type { DslJourneySummary, QueueJob, QueueSummary, SimpleJourneySummary } from "@/types/api";

type ViewMode = "grid" | "list";

type RunSnapshot = {
  running: ReadonlySet<string>;
  bulk: boolean;
  message: string | null;
};

let runSnapshot: RunSnapshot = {
  running: new Set(),
  bulk: false,
  message: null,
};
const runListeners = new Set<() => void>();

function emitRunSnapshot(next: RunSnapshot) {
  runSnapshot = next;
  runListeners.forEach((l) => l());
}

function subscribeRunSnapshot(onStoreChange: () => void) {
  runListeners.add(onStoreChange);
  return () => {
    runListeners.delete(onStoreChange);
  };
}

function getRunSnapshot() {
  return runSnapshot;
}

function setRunMessage(message: string | null) {
  emitRunSnapshot({ ...runSnapshot, message });
}

function markJourneyRunning(journeyId: string) {
  const running = new Set(runSnapshot.running);
  running.add(journeyId);
  emitRunSnapshot({ ...runSnapshot, running });
}

function markJourneyIdle(journeyId: string) {
  const running = new Set(runSnapshot.running);
  running.delete(journeyId);
  emitRunSnapshot({ ...runSnapshot, running });
}

function JourneyGrid({ children }: { children: React.ReactNode }) {
  return <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{children}</div>;
}

type JourneyLive = {
  badge: string;
  total: number;
  done: number;
  running: number;
  queued: number;
  failed: number;
  jobId: string;
};

function journeyLive(
  journey: SimpleJourneySummary,
  creating: boolean,
  queueJobs: QueueJob[],
): JourneyLive {
  const base = journeyListStats(journey);
  const mine = queueJobs.filter((j) => j.journey_id === journey.journeyId);
  const running = mine.filter((j) => j.state === "running" || j.state === "claimed").length;
  const queued = mine.filter((j) => j.state === "waiting").length;
  const creatingSlot = creating && mine.length === 0 ? 1 : 0;
  const inFlight = running + queued + creatingSlot;
  const active =
    mine.find((j) => j.state === "running" || j.state === "claimed") ??
    mine.find((j) => j.state === "waiting");
  let badge = journey.status;
  if (running) badge = "running";
  else if (queued) badge = "queued";
  else if (creating) badge = "queuing";
  return {
    badge,
    total: Math.max(base.total, base.done + base.failed + inFlight),
    done: base.done,
    running,
    queued: queued + creatingSlot,
    failed: base.failed,
    jobId: active?.job_id ?? "",
  };
}

/** Share of finished jobs that succeeded, as one thin bar plus a sentence. */
function OutcomeBar({ live }: { live: JourneyLive }) {
  const finished = live.done + live.failed;
  const okPct = finished > 0 ? (live.done / finished) * 100 : 0;
  const failPct = finished > 0 ? 100 - okPct : 0;
  return (
    <div>
      <div className="flex h-1.5 overflow-hidden rounded-full bg-surface-3" aria-hidden="true">
        <span className="h-full bg-primary transition-[width] duration-slow ease-brand-out" style={{ width: `${okPct}%` }} />
        <span className="h-full bg-destructive transition-[width] duration-slow ease-brand-out" style={{ width: `${failPct}%` }} />
      </div>
      <p className="num mt-2 text-xs text-muted-foreground">
        <span className="font-medium text-foreground">{live.total.toLocaleString()}</span> jobs ·{" "}
        {live.done.toLocaleString()} done
        {live.running > 0 ? <> · <span className="text-primary dark:text-brand-hi">{live.running} running</span></> : null}
        {live.queued > 0 ? <> · <span className="text-warning">{live.queued} waiting</span></> : null}
        {live.failed > 0 ? <> · <span className="text-destructive">{live.failed.toLocaleString()} failed</span></> : null}
      </p>
    </div>
  );
}

/** Journeys with nothing in flight report a legacy "pending" status; show that as idle. */
function JourneyStatus({ badge }: { badge: string }) {
  if (badge.toLowerCase() === "pending") return <StatusPill tone="neutral">Idle</StatusPill>;
  return <StatusPill status={badge} />;
}

type JourneyCardProps = {
  journey: SimpleJourneySummary;
  selected: boolean;
  onToggleSelect: () => void;
  onRun: () => void;
  onCancel: () => void;
  isRunning: boolean;
  isCancelling: boolean;
  live: JourneyLive;
};

function JourneyCard({
  journey,
  selected,
  onToggleSelect,
  onRun,
  onCancel,
  isRunning,
  isCancelling,
  live,
}: JourneyCardProps) {
  return (
    <article
      className={cn(
        "group flex min-w-0 flex-col rounded-xl border bg-card p-5 shadow-xs transition-[border-color,box-shadow,transform] duration-200 ease-brand hover:-translate-y-0.5 hover:shadow-md",
        selected ? "border-brand/60 ring-1 ring-brand/40" : "border-border hover:border-brand/40",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-2.5">
          <input
            type="checkbox"
            aria-label={`Select ${journey.name}`}
            checked={selected}
            onChange={onToggleSelect}
            className="check mt-0.5"
          />
          <span className="min-w-0">
            <Link to={`/journeys/${journey.journeyId}`} className="block truncate text-md font-medium text-foreground hover:text-primary dark:hover:text-brand-hi">
              {journey.name}
            </Link>
            <span className="mono-id">{journey.journeyId}</span>
          </span>
        </div>
        <JourneyStatus badge={live.badge} />
      </div>

      <p className="mt-3 line-clamp-2 min-h-10 text-sm text-muted-foreground">
        {journey.description || "No description."}
      </p>

      <div className="mt-4">
        <OutcomeBar live={live} />
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-border pt-4">
        <Button
          size="sm"
          disabled={isRunning || isCancelling}
          onClick={onRun}
          data-testid={`run-journey-${journey.journeyId}`}
        >
          <Icon name={isRunning ? "spinner" : "play"} className={isRunning ? "animate-spin" : undefined} />
          Run
        </Button>
        {live.jobId ? (
          <Button
            size="sm"
            variant="outline"
            disabled={isCancelling}
            onClick={onCancel}
            data-testid={`cancel-journey-${journey.journeyId}`}
          >
            <Icon name={isCancelling ? "spinner" : "close"} className={isCancelling ? "animate-spin" : "h-3 w-3"} />
            Cancel
          </Button>
        ) : null}
        <Button variant="ghost" size="sm" className="ml-auto" asChild>
          <Link to={`/journeys/${journey.journeyId}`}>
            Open
            <Icon name="arrow-right" className="h-3.5 w-3.5" />
          </Link>
        </Button>
      </div>
    </article>
  );
}

type JourneyListRowProps = JourneyCardProps;

function JourneyListRow({
  journey,
  selected,
  onToggleSelect,
  onRun,
  onCancel,
  isRunning,
  isCancelling,
  live,
}: JourneyListRowProps) {
  return (
    <tr className={selected ? "!bg-primary/5" : undefined}>
      <td>
        <input
          type="checkbox"
          aria-label={`Select ${journey.name}`}
          checked={selected}
          onChange={onToggleSelect}
          className="check"
        />
      </td>
      <td className="max-w-[360px]">
        <Link to={`/journeys/${journey.journeyId}`} className="block truncate font-medium text-foreground hover:text-primary dark:hover:text-brand-hi">
          {journey.name}
        </Link>
        <span className="mono-id">{journey.journeyId}</span>
      </td>
      <td>
        <JourneyStatus badge={live.badge} />
      </td>
      <td className="r num">{live.total.toLocaleString()}</td>
      <td className="r num">{live.done.toLocaleString()}</td>
      <td className={cn("r num", live.running > 0 ? "text-primary dark:text-brand-hi" : "text-subtle-foreground")}>{live.running}</td>
      <td className={cn("r num", live.queued > 0 ? "text-warning" : "text-subtle-foreground")}>{live.queued}</td>
      <td className={cn("r num", live.failed > 0 ? "text-destructive" : "text-subtle-foreground")}>{live.failed.toLocaleString()}</td>
      <td>
        <div className="flex justify-end gap-2">
          <Button size="sm" disabled={isRunning || isCancelling} onClick={onRun}>
            <Icon name={isRunning ? "spinner" : "play"} className={isRunning ? "animate-spin" : undefined} />
            Run
          </Button>
          {live.jobId ? (
            <Button size="sm" variant="outline" disabled={isCancelling} onClick={onCancel}>
              <Icon name={isCancelling ? "spinner" : "close"} className={isCancelling ? "animate-spin" : "h-3 w-3"} />
              Cancel
            </Button>
          ) : null}
          <Button variant="outline" size="sm" asChild>
            <Link to={`/journeys/${journey.journeyId}`}>Open</Link>
          </Button>
        </div>
      </td>
    </tr>
  );
}

function DslJourneyCard({ journey }: { journey: DslJourneySummary }) {
  return (
    <article className="flex min-w-0 flex-col rounded-xl border border-border bg-card p-5 shadow-xs transition-[border-color,box-shadow,transform] duration-200 ease-brand hover:-translate-y-0.5 hover:border-brand/40 hover:shadow-md">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-md font-medium text-foreground">{journey.display_name || journey.id}</h3>
          <p className="mono-id truncate">{journey.id}</p>
        </div>
        <span className="num shrink-0 rounded border border-border-strong px-1.5 py-px text-xs text-muted-foreground">v{journey.version}</span>
      </div>
      <div className="mt-4 border-t border-border pt-4">
        <Button variant="outline" size="sm" asChild>
          <Link to={`/journeys/${journey.id}/studio`}>
            <Icon name="file-code" />
            Edit YAML
          </Link>
        </Button>
      </div>
    </article>
  );
}

type JourneyFilter = "all" | "active" | "failures" | "idle";

export function JourneysListPage() {
  const queryClient = useQueryClient();
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<JourneyFilter>("all");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [cancellingIds, setCancellingIds] = useState<Set<string>>(new Set());
  const { running: runningIds, bulk: bulkRunning, message: runMessage } = useSyncExternalStore(
    subscribeRunSnapshot,
    getRunSnapshot,
    getRunSnapshot,
  );

  const queueQuery = useQuery({
    queryKey: ["queue", "jobs"],
    queryFn: () => api.queueJobs("all", 200),
    refetchInterval: 2_000,
    retry: 1,
  });
  const queueJobs = queueQuery.data?.jobs ?? [];
  const queueBusy = bulkRunning || queueJobs.length > 0;

  const [dslQuery, simpleQuery] = useQueries({
    queries: [
      { queryKey: ["dsl-journeys"], queryFn: api.listDslJourneys },
      {
        queryKey: ["simple-journeys"],
        queryFn: api.listSimpleJourneys,
        refetchInterval: queueBusy ? 3_000 : 15_000,
      },
    ],
  });

  const liveByJourney = useMemo(() => {
    const map = new Map<string, JourneyLive>();
    for (const journey of simpleQuery.data ?? []) {
      map.set(
        journey.journeyId,
        journeyLive(journey, runningIds.has(journey.journeyId), queueJobs),
      );
    }
    return map;
  }, [simpleQuery.data, runningIds, queueJobs]);

  const isLoading = dslQuery.isLoading || simpleQuery.isLoading;
  const error = dslQuery.error ?? simpleQuery.error;
  const dslJourneys = dslQuery.data ?? [];
  const simpleJourneys = simpleQuery.data ?? [];
  const hasAny = dslJourneys.length > 0 || simpleJourneys.length > 0;

  const invalidateAfterRun = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["simple-journeys"] });
    void queryClient.invalidateQueries({ queryKey: ["runs"] });
    void queryClient.invalidateQueries({ queryKey: ["queue"] });
  }, [queryClient]);

  const runOne = useCallback(
    async (journeyId: string) => {
      markJourneyRunning(journeyId);
      try {
        const job = await api.runJourneyJob(journeyId);
        setRunMessage(`Started ${journeyId} → ${job.id}`);
        invalidateAfterRun();
        return { journeyId, ok: true as const, jobId: job.id };
      } catch (err) {
        setRunMessage(`Failed ${journeyId}: ${String(err)}`);
        return { journeyId, ok: false as const, error: String(err) };
      } finally {
        markJourneyIdle(journeyId);
      }
    },
    [invalidateAfterRun],
  );

  const runMany = useCallback(
    async (journeyIds: string[]) => {
      if (journeyIds.length === 0) return;
      const running = new Set(runSnapshot.running);
      journeyIds.forEach((id) => running.add(id));
      emitRunSnapshot({
        running,
        bulk: true,
        message: `Queuing ${journeyIds.length} job(s)…`,
      });
      try {
        const result = await api.runJourneyJobsBulk(journeyIds);
        let capacity = queryClient.getQueryData<QueueSummary>(["queue", "summary"])?.running_capacity;
        if (capacity == null) {
          try {
            capacity = (await api.queueSummary()).running_capacity;
          } catch {
            capacity = undefined;
          }
        }
        emitRunSnapshot({
          running: new Set(),
          bulk: false,
          message:
            result.failed > 0
              ? `Queued ${result.queued} job(s), ${result.failed} failed`
              : `Queued ${result.queued} job(s) — workers take ${capacity ?? 9}, the rest wait`,
        });
        invalidateAfterRun();
      } catch (err) {
        emitRunSnapshot({
          running: new Set(),
          bulk: false,
          message: `Failed to queue jobs: ${String(err)}`,
        });
      }
      setSelected(new Set());
    },
    [invalidateAfterRun, queryClient],
  );

  const cancelOne = useCallback(
    async (journeyId: string, jobId: string) => {
      if (!jobId) return;
      setCancellingIds((prev) => new Set(prev).add(journeyId));
      try {
        await api.cancelStageJob(journeyId, jobId);
        setRunMessage(`Cancelled ${jobId}`);
        invalidateAfterRun();
      } catch (err) {
        setRunMessage(`Failed to cancel ${jobId}: ${String(err)}`);
      } finally {
        setCancellingIds((prev) => {
          const next = new Set(prev);
          next.delete(journeyId);
          return next;
        });
      }
    },
    [invalidateAfterRun],
  );

  const toggleSelect = useCallback((journeyId: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(journeyId)) next.delete(journeyId);
      else next.add(journeyId);
      return next;
    });
  }, []);

  const toggleSelectAll = useCallback(() => {
    const allIds = simpleJourneys.map((j) => j.journeyId);
    setSelected((prev) => {
      const allSelected = allIds.length > 0 && allIds.every((id) => prev.has(id));
      return allSelected ? new Set() : new Set(allIds);
    });
  }, [simpleJourneys]);

  const selectedCount = selected.size;
  const allSimpleSelected =
    simpleJourneys.length > 0 && simpleJourneys.every((j) => selected.has(j.journeyId));

  const journeyRowProps = (journey: SimpleJourneySummary) => ({
    journey,
    selected: selected.has(journey.journeyId),
    onToggleSelect: () => toggleSelect(journey.journeyId),
    onRun: () => void runOne(journey.journeyId),
    onCancel: () => {
      const live = liveByJourney.get(journey.journeyId);
      if (live?.jobId) void cancelOne(journey.journeyId, live.jobId);
    },
    isRunning:
      runningIds.has(journey.journeyId) ||
      (liveByJourney.get(journey.journeyId)?.running ?? 0) > 0,
    isCancelling: cancellingIds.has(journey.journeyId),
    live: liveByJourney.get(journey.journeyId) ?? journeyLive(journey, runningIds.has(journey.journeyId), queueJobs),
  });

  const liveOf = (j: SimpleJourneySummary) =>
    liveByJourney.get(j.journeyId) ?? journeyLive(j, runningIds.has(j.journeyId), queueJobs);
  const counts = { active: 0, failures: 0, idle: 0 };
  for (const j of simpleJourneys) {
    const live = liveOf(j);
    if (live.running + live.queued > 0) counts.active += 1;
    else counts.idle += 1;
    if (live.failed > 0) counts.failures += 1;
  }
  const q = search.trim().toLowerCase();
  const matches = (text: string) => !q || text.toLowerCase().includes(q);
  const visibleJourneys = simpleJourneys.filter((j) => {
    if (!matches(`${j.name} ${j.journeyId} ${j.description ?? ""} ${j.odaComponentType ?? ""}`)) return false;
    const live = liveOf(j);
    if (filter === "active") return live.running + live.queued > 0;
    if (filter === "failures") return live.failed > 0;
    if (filter === "idle") return live.running + live.queued === 0;
    return true;
  });
  const visibleDsl = dslJourneys.filter((j) => matches(`${j.display_name} ${j.id}`));
  const messageTone = runMessage && /^Failed/.test(runMessage) ? "danger" : "info";

  return (
    <div className="space-y-5">
      <PageHeader
        title="Journeys"
        description="Stage-based pipelines and YAML-defined DSL journeys."
        actions={
          <>
            {simpleJourneys.length > 0 ? (
              <Button
                variant="outline"
                size="sm"
                disabled={bulkRunning || runningIds.size > 0}
                onClick={() => void runMany(simpleJourneys.map((j) => j.journeyId))}
                data-testid="run-all-journeys"
              >
                <Icon name="play" />
                Run all ({simpleJourneys.length})
              </Button>
            ) : null}
            <Button size="sm" asChild>
              <Link to="/journeys/new/studio">
                <Icon name="plus" />
                New DSL journey
              </Link>
            </Button>
          </>
        }
      />

      {hasAny ? (
        <Toolbar>
          <SearchInput value={search} onChange={setSearch} placeholder="Search journeys" />
          {simpleJourneys.length > 0 ? (
            <Chips<JourneyFilter>
              label="Filter journeys"
              value={filter}
              onChange={setFilter}
              options={[
                { value: "all", label: "All", count: simpleJourneys.length },
                { value: "active", label: "Active now", count: counts.active },
                { value: "failures", label: "With failures", count: counts.failures },
                { value: "idle", label: "Idle", count: counts.idle },
              ]}
            />
          ) : null}
          <ToolbarSpacer />
          {simpleJourneys.length > 0 ? (
            <>
              <label className="flex cursor-pointer items-center gap-2 text-sm text-muted-foreground">
                <input
                  type="checkbox"
                  aria-label="Select all journeys"
                  checked={allSimpleSelected}
                  onChange={toggleSelectAll}
                  className="check"
                />
                Select all
              </label>
              <Segmented<ViewMode>
                label="View"
                value={viewMode}
                onChange={setViewMode}
                options={[
                  { value: "grid", label: <span className="flex items-center gap-1.5" aria-label="Grid view"><Icon name="grid" className="h-3.5 w-3.5" />Cards</span> },
                  { value: "list", label: <span className="flex items-center gap-1.5" aria-label="List view"><Icon name="list" className="h-3.5 w-3.5" />Table</span> },
                ]}
              />
            </>
          ) : null}
        </Toolbar>
      ) : null}

      {selectedCount > 0 ? (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border-strong bg-surface-2/70 px-4 py-2.5">
          <span className="text-sm text-foreground">
            <span className="num font-medium">{selectedCount}</span> selected
          </span>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => setSelected(new Set())}>
              Clear selection
            </Button>
            <Button
              size="sm"
              disabled={bulkRunning}
              onClick={() => void runMany(Array.from(selected))}
              data-testid="bulk-run-journeys"
            >
              <Icon name={bulkRunning ? "spinner" : "play"} className={bulkRunning ? "animate-spin" : undefined} />
              Run selected ({selectedCount})
            </Button>
          </div>
        </div>
      ) : null}

      {runMessage ? (
        <Notice tone={messageTone} data-testid="run-message">
          {runMessage}
        </Notice>
      ) : null}

      {isLoading ? (
        <TableShell>
          <SkeletonRows rows={6} />
        </TableShell>
      ) : error ? (
        <InlineError>Could not load journeys. {String(error)}</InlineError>
      ) : !hasAny ? (
        <EmptyState
          icon="route"
          title="No journeys yet"
          description="Seed sample journeys for local dev or create a DSL journey."
          action={
            <Button asChild>
              <Link to="/journeys/new/studio">Create DSL journey</Link>
            </Button>
          }
        />
      ) : (
        <>
          {simpleJourneys.length > 0 ? (
            <section className="space-y-3" data-testid="simple-journeys">
              {visibleJourneys.length === 0 ? (
                <EmptyState
                  icon="search"
                  title="No journeys match"
                  description="Try a different search or filter."
                  action={
                    <button type="button" className="link" onClick={() => { setSearch(""); setFilter("all"); }}>
                      Clear filters
                    </button>
                  }
                />
              ) : viewMode === "grid" ? (
                <JourneyGrid>
                  {visibleJourneys.map((j) => (
                    <JourneyCard key={j.journeyId} {...journeyRowProps(j)} />
                  ))}
                </JourneyGrid>
              ) : (
                <TableShell>
                  <table className="tbl">
                    <thead>
                      <tr>
                        <th className="w-10" />
                        <th>Journey</th>
                        <th>Status</th>
                        <th className="r">Jobs</th>
                        <th className="r">Done</th>
                        <th className="r">Run</th>
                        <th className="r">Wait</th>
                        <th className="r">Failed</th>
                        <th className="r">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {visibleJourneys.map((j) => (
                        <JourneyListRow key={j.journeyId} {...journeyRowProps(j)} />
                      ))}
                    </tbody>
                  </table>
                </TableShell>
              )}
            </section>
          ) : null}

          {visibleDsl.length > 0 ? (
            <section className="space-y-3 pt-2" data-testid="dsl-journeys">
              <div>
                <h3 className="text-md font-medium text-foreground">DSL journeys</h3>
                <p className="text-sm text-muted-foreground">YAML-defined journeys editable in the studio.</p>
              </div>
              <JourneyGrid>
                {visibleDsl.map((j) => (
                  <DslJourneyCard key={`${j.id}-${j.version}`} journey={j} />
                ))}
              </JourneyGrid>
            </section>
          ) : null}
        </>
      )}
    </div>
  );
}
