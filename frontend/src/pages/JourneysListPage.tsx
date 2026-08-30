import { useCallback, useState } from "react";
import { useQueries, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { LayoutGrid, List, Loader2, Play, Plus } from "lucide-react";

import { EmptyState } from "@/components/EmptyState";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { journeyListStats } from "@/lib/stageJourney";
import { api } from "@/services/api";
import type { DslJourneySummary, SimpleJourneySummary } from "@/types/api";

type ViewMode = "grid" | "list";

function JourneyGrid({ children }: { children: React.ReactNode }) {
  return <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{children}</div>;
}

type JourneyCardProps = {
  journey: SimpleJourneySummary;
  selected: boolean;
  onToggleSelect: () => void;
  onRun: () => void;
  isRunning: boolean;
};

function JourneyCard({ journey, selected, onToggleSelect, onRun, isRunning }: JourneyCardProps) {
  const stats = journeyListStats(journey);

  return (
    <Card className={selected ? "ring-2 ring-primary/60" : undefined}>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-start gap-2 min-w-0">
            <input
              type="checkbox"
              aria-label={`Select ${journey.name}`}
              checked={selected}
              onChange={onToggleSelect}
              className="mt-1 rounded border-border shrink-0"
            />
            <CardTitle className="text-base">{journey.name}</CardTitle>
          </div>
          <StatusBadge status={journey.status} />
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {journey.description ? (
          <p className="text-sm text-muted-foreground line-clamp-2">{journey.description}</p>
        ) : null}
        <div className="grid grid-cols-4 gap-2 text-center text-xs">
          <div>
            <p className="text-muted-foreground">Jobs</p>
            <p className="font-semibold">{stats.total}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Done</p>
            <p className="font-semibold text-emerald-400">{stats.done}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Running</p>
            <p className="font-semibold text-blue-400">{stats.running}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Failed</p>
            <p className="font-semibold text-red-400">{stats.failed}</p>
          </div>
        </div>
        <p className="text-xs text-muted-foreground font-mono">{journey.journeyId}</p>
        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            disabled={isRunning}
            onClick={onRun}
            data-testid={`run-journey-${journey.journeyId}`}
          >
            {isRunning ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Play className="h-4 w-4" />
            )}
            Run
          </Button>
          <Button variant="outline" size="sm" asChild>
            <Link to={`/journeys/${journey.journeyId}`}>Open</Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

type JourneyListRowProps = JourneyCardProps;

function JourneyListRow({ journey, selected, onToggleSelect, onRun, isRunning }: JourneyListRowProps) {
  const stats = journeyListStats(journey);

  return (
    <tr className={`border-b border-border/50 ${selected ? "bg-primary/5" : ""}`}>
      <td className="py-2 pr-2">
        <input
          type="checkbox"
          aria-label={`Select ${journey.name}`}
          checked={selected}
          onChange={onToggleSelect}
          className="rounded border-border"
        />
      </td>
      <td className="py-2 pr-4">
        <Link to={`/journeys/${journey.journeyId}`} className="font-medium text-primary hover:underline">
          {journey.name}
        </Link>
        {journey.description ? (
          <p className="text-xs text-muted-foreground line-clamp-1 mt-0.5">{journey.description}</p>
        ) : null}
      </td>
      <td className="py-2 pr-4 font-mono text-xs text-muted-foreground">{journey.journeyId}</td>
      <td className="py-2 pr-4">
        <StatusBadge status={journey.status} />
      </td>
      <td className="py-2 pr-4 text-center">{stats.total}</td>
      <td className="py-2 pr-4 text-center text-emerald-400">{stats.done}</td>
      <td className="py-2 pr-4 text-center text-blue-400">{stats.running}</td>
      <td className="py-2 pr-4 text-center text-red-400">{stats.failed}</td>
      <td className="py-2">
        <div className="flex gap-2">
          <Button size="sm" disabled={isRunning} onClick={onRun}>
            {isRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            Run
          </Button>
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
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">{journey.display_name || journey.id}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <p className="text-xs text-muted-foreground font-mono">{journey.id}</p>
        <p className="text-xs">v{journey.version}</p>
        <Button variant="outline" size="sm" asChild>
          <Link to={`/journeys/${journey.id}/studio`}>Edit YAML</Link>
        </Button>
      </CardContent>
    </Card>
  );
}

export function JourneysListPage() {
  const queryClient = useQueryClient();
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [runningIds, setRunningIds] = useState<Set<string>>(new Set());
  const [bulkRunning, setBulkRunning] = useState(false);
  const [runMessage, setRunMessage] = useState<string | null>(null);

  const [dslQuery, simpleQuery] = useQueries({
    queries: [
      { queryKey: ["dsl-journeys"], queryFn: api.listDslJourneys },
      { queryKey: ["simple-journeys"], queryFn: api.listSimpleJourneys },
    ],
  });

  const isLoading = dslQuery.isLoading || simpleQuery.isLoading;
  const error = dslQuery.error ?? simpleQuery.error;
  const dslJourneys = dslQuery.data ?? [];
  const simpleJourneys = simpleQuery.data ?? [];
  const hasAny = dslJourneys.length > 0 || simpleJourneys.length > 0;

  const invalidateAfterRun = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["simple-journeys"] });
    void queryClient.invalidateQueries({ queryKey: ["runs"] });
  }, [queryClient]);

  const runOne = useCallback(
    async (journeyId: string) => {
      setRunningIds((prev) => new Set(prev).add(journeyId));
      try {
        const job = await api.runJourneyJob(journeyId);
        setRunMessage(`Started ${journeyId} → ${job.id}`);
        invalidateAfterRun();
        return { journeyId, ok: true as const, jobId: job.id };
      } catch (err) {
        setRunMessage(`Failed ${journeyId}: ${String(err)}`);
        return { journeyId, ok: false as const, error: String(err) };
      } finally {
        setRunningIds((prev) => {
          const next = new Set(prev);
          next.delete(journeyId);
          return next;
        });
      }
    },
    [invalidateAfterRun],
  );

  const runMany = useCallback(
    async (journeyIds: string[]) => {
      if (journeyIds.length === 0) return;
      setBulkRunning(true);
      setRunMessage(`Starting ${journeyIds.length} job(s)…`);
      const results = await Promise.all(journeyIds.map((id) => runOne(id)));
      const started = results.filter((r) => r.ok).length;
      const failed = results.length - started;
      setRunMessage(
        failed > 0
          ? `Started ${started} job(s), ${failed} failed`
          : `Started ${started} job(s) concurrently`,
      );
      setBulkRunning(false);
      setSelected(new Set());
    },
    [runOne],
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
    isRunning: runningIds.has(journey.journeyId),
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold">Journeys</h2>
          <p className="text-sm text-muted-foreground">
            Stage-based pipelines and YAML-defined DSL journeys.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {simpleJourneys.length > 0 ? (
            <div className="flex rounded-md border border-border overflow-hidden">
              <Button
                type="button"
                variant={viewMode === "grid" ? "default" : "ghost"}
                size="sm"
                className="rounded-none"
                onClick={() => setViewMode("grid")}
                aria-label="Grid view"
              >
                <LayoutGrid className="h-4 w-4" />
              </Button>
              <Button
                type="button"
                variant={viewMode === "list" ? "default" : "ghost"}
                size="sm"
                className="rounded-none"
                onClick={() => setViewMode("list")}
                aria-label="List view"
              >
                <List className="h-4 w-4" />
              </Button>
            </div>
          ) : null}
          {selectedCount > 0 ? (
            <Button
              size="sm"
              disabled={bulkRunning}
              onClick={() => void runMany(Array.from(selected))}
              data-testid="bulk-run-journeys"
            >
              {bulkRunning ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              Run selected ({selectedCount})
            </Button>
          ) : null}
          {simpleJourneys.length > 0 ? (
            <Button
              variant="outline"
              size="sm"
              disabled={bulkRunning || runningIds.size > 0}
              onClick={() => void runMany(simpleJourneys.map((j) => j.journeyId))}
              data-testid="run-all-journeys"
            >
              Run all ({simpleJourneys.length})
            </Button>
          ) : null}
          <Button asChild>
            <Link to="/journeys/new/studio">
              <Plus className="h-4 w-4" />
              New DSL journey
            </Link>
          </Button>
        </div>
      </div>

      {runMessage ? (
        <p className="text-sm text-muted-foreground" data-testid="run-message">
          {runMessage}
        </p>
      ) : null}

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading journeys…</p>
      ) : error ? (
        <EmptyState title="Could not load journeys" description={String(error)} />
      ) : !hasAny ? (
        <EmptyState
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
              {viewMode === "grid" ? (
                <JourneyGrid>
                  {simpleJourneys.map((j) => (
                    <JourneyCard key={j.journeyId} {...journeyRowProps(j)} />
                  ))}
                </JourneyGrid>
              ) : (
                <Card>
                  <CardContent className="pt-4">
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="text-left text-muted-foreground border-b border-border">
                            <th className="py-2 pr-2 w-8">
                              <input
                                type="checkbox"
                                aria-label="Select all journeys"
                                checked={allSimpleSelected}
                                onChange={toggleSelectAll}
                                className="rounded border-border"
                              />
                            </th>
                            <th className="py-2 pr-4">Journey</th>
                            <th className="py-2 pr-4">ID</th>
                            <th className="py-2 pr-4">Status</th>
                            <th className="py-2 pr-4 text-center">Jobs</th>
                            <th className="py-2 pr-4 text-center">Done</th>
                            <th className="py-2 pr-4 text-center">Running</th>
                            <th className="py-2 pr-4 text-center">Failed</th>
                            <th className="py-2">Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {simpleJourneys.map((j) => (
                            <JourneyListRow key={j.journeyId} {...journeyRowProps(j)} />
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>
              )}
            </section>
          ) : null}

          {dslJourneys.length > 0 ? (
            <section className="space-y-3" data-testid="dsl-journeys">
              <div>
                <h3 className="text-sm font-medium">DSL journeys</h3>
                <p className="text-xs text-muted-foreground">YAML-defined journeys editable in the studio.</p>
              </div>
              <JourneyGrid>
                {dslJourneys.map((j) => (
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
