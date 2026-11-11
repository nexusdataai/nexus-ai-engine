import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { DateTimePicker } from "@/components/DateTimePicker";
import { Icon } from "@/components/ds/Icon";
import { Chips, EmptyState, InlineError, PageHeader, SearchInput, SkeletonRows, StatusPill, TableShell, Toolbar, ToolbarSpacer, toneOf } from "@/components/ds/kit";
import { Button } from "@/components/ui/button";
import { api } from "@/services/api";
import { truncateId } from "@/lib/utils";
import { relativeTime } from "@/utils/time";
import type { UnifiedRunRow } from "@/types/stageJourney";

const PAGE_SIZE = 100;

type StatusFilter = "all" | "running" | "succeeded" | "failed" | "other";

function runHref(row: UnifiedRunRow): string {
  if (row.kind === "stage_job") {
    return `/executions/stage/${row.journeyId}/${row.id}`;
  }
  return `/executions/${row.id}`;
}

function runLabel(row: UnifiedRunRow): string {
  return row.kind === "stage_job" ? row.id : truncateId(row.id, 12);
}

function rowKey(row: UnifiedRunRow): string {
  return `${row.kind}-${row.journeyId}-${row.id}`;
}

function isDeletable(row: UnifiedRunRow): boolean {
  if (row.kind !== "stage_job") return false;
  const status = row.status.toLowerCase();
  return !["running", "pending", "in_progress"].includes(status);
}

function parseRunTimestamp(row: UnifiedRunRow): number | null {
  if (row.kind !== "stage_job" || !row.startedAt) return null;
  const value = Date.parse(row.startedAt);
  return Number.isNaN(value) ? null : value;
}

function formatRunTime(row: UnifiedRunRow): string {
  const ts = parseRunTimestamp(row);
  if (ts == null) return "—";
  return new Date(ts).toLocaleString();
}

function statusGroup(row: UnifiedRunRow): Exclude<StatusFilter, "all"> {
  const tone = toneOf(row.status);
  if (tone === "info") return "running";
  if (tone === "success") return "succeeded";
  if (tone === "danger") return "failed";
  return "other";
}

export function ExecutionsListPage() {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [fromFilter, setFromFilter] = useState<Date | null>(null);
  const [toFilter, setToFilter] = useState<Date | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [visible, setVisible] = useState(PAGE_SIZE);

  const { data, isLoading, isFetching, error, refetch } = useQuery({
    queryKey: ["runs"],
    queryFn: () => api.listAllRuns(),
    refetchInterval: 5_000,
  });

  const rows = data ?? [];

  const dateRows = useMemo(() => {
    const fromMs = fromFilter?.getTime() ?? null;
    const toMs = toFilter ? toFilter.getTime() + 59_999 : null;
    const q = search.trim().toLowerCase();
    return rows.filter((row) => {
      if (q) {
        const hay = `${row.id} ${row.journeyId} ${row.kind === "stage_job" ? row.journeyName ?? "" : ""} ${row.kind === "stage_job" ? row.stageId ?? "" : ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      const ts = parseRunTimestamp(row);
      if (ts == null) {
        return fromMs == null && toMs == null;
      }
      if (fromMs != null && ts < fromMs) return false;
      if (toMs != null && ts > toMs) return false;
      return true;
    });
  }, [rows, fromFilter, toFilter, search]);

  const counts = useMemo(() => {
    const c = { running: 0, succeeded: 0, failed: 0, other: 0 };
    for (const row of dateRows) c[statusGroup(row)] += 1;
    return c;
  }, [dateRows]);

  const filteredRows = useMemo(
    () => (statusFilter === "all" ? dateRows : dateRows.filter((row) => statusGroup(row) === statusFilter)),
    [dateRows, statusFilter],
  );
  const pageRows = filteredRows.slice(0, visible);

  const deletableRows = useMemo(() => filteredRows.filter(isDeletable), [filteredRows]);

  const running = rows.filter((r) => {
    const s = r.status.toLowerCase();
    return s === "running" || s === "in_progress";
  });

  const deleteMutation = useMutation({
    mutationFn: async (jobs: UnifiedRunRow[]) => {
      const byJourney = new Map<string, string[]>();
      for (const row of jobs) {
        if (row.kind !== "stage_job") continue;
        const list = byJourney.get(row.journeyId) ?? [];
        list.push(row.id);
        byJourney.set(row.journeyId, list);
      }
      const results = await Promise.all(
        [...byJourney.entries()].map(([journeyId, jobIds]) => api.batchDeleteStageJobs(journeyId, jobIds)),
      );
      return results;
    },
    onSuccess: () => {
      setSelected(new Set());
      queryClient.invalidateQueries({ queryKey: ["runs"] });
    },
  });

  const toggleRow = (row: UnifiedRunRow) => {
    if (!isDeletable(row)) return;
    const key = rowKey(row);
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const toggleAllDeletable = () => {
    const keys = deletableRows.map(rowKey);
    const allSelected = keys.length > 0 && keys.every((key) => selected.has(key));
    if (allSelected) {
      setSelected(new Set());
    } else {
      setSelected(new Set(keys));
    }
  };

  const selectedRows = deletableRows.filter((row) => selected.has(rowKey(row)));

  const handleDelete = () => {
    if (selectedRows.length === 0) return;
    const confirmed = window.confirm(
      `Delete ${selectedRows.length} execution job(s)? This removes DynamoDB records and S3 logs/reports permanently.`,
    );
    if (!confirmed) return;
    deleteMutation.mutate(selectedRows);
  };

  const clearFilters = () => {
    setFromFilter(null);
    setToFilter(null);
    setSearch("");
    setStatusFilter("all");
  };
  const hasFilters = Boolean(fromFilter || toFilter || search || statusFilter !== "all");

  return (
    <div className="space-y-5">
      <PageHeader
        title="Executions"
        description={
          <>
            Stage jobs and DSL runs in one monitor — auto-refreshes every 5s.{" "}
            {!isLoading && (
              <span className="text-foreground">
                <span className="num font-medium">{rows.length.toLocaleString()}</span> runs,{" "}
                <span className="num font-medium">{running.length}</span> running now.
              </span>
            )}
          </>
        }
        actions={
          <>
            <Button variant="outline" size="sm" asChild>
              <Link to="/journeys">
                <Icon name="route" />
                Browse journeys
              </Link>
            </Button>
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              <Icon name="refresh" className={isFetching ? "animate-spin" : undefined} />
              Refresh
            </Button>
          </>
        }
      />

      <Toolbar>
        <SearchInput value={search} onChange={(v) => { setSearch(v); setVisible(PAGE_SIZE); }} placeholder="Search run or journey" />
        <Chips<StatusFilter>
          label="Filter by status"
          value={statusFilter}
          onChange={(v) => { setStatusFilter(v); setVisible(PAGE_SIZE); }}
          options={[
            { value: "all", label: "All", count: dateRows.length },
            { value: "running", label: "Running", count: counts.running },
            { value: "succeeded", label: "Succeeded", count: counts.succeeded },
            { value: "failed", label: "Failed", count: counts.failed },
            ...(counts.other > 0 ? [{ value: "other" as const, label: "Other", count: counts.other }] : []),
          ]}
        />
        <ToolbarSpacer />
        <DateTimePicker label="From" value={fromFilter} onChange={setFromFilter} />
        <DateTimePicker label="To" value={toFilter} onChange={setToFilter} />
        {hasFilters && (
          <Button variant="ghost" size="sm" onClick={clearFilters}>
            Clear filters
          </Button>
        )}
      </Toolbar>

      {selectedRows.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border-strong bg-surface-2/70 px-4 py-2.5">
          <span className="text-sm text-foreground">
            <span className="num font-medium">{selectedRows.length}</span> selected
          </span>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => setSelected(new Set())}>
              Clear selection
            </Button>
            <Button variant="destructive" size="sm" disabled={deleteMutation.isPending} onClick={handleDelete}>
              <Icon name="trash" />
              {deleteMutation.isPending ? "Deleting…" : `Delete selected (${selectedRows.length})`}
            </Button>
          </div>
        </div>
      )}
      {deleteMutation.isError && <InlineError>{String(deleteMutation.error)}</InlineError>}

      {isLoading ? (
        <TableShell>
          <SkeletonRows rows={8} />
        </TableShell>
      ) : error ? (
        <InlineError onRetry={() => refetch()}>Failed to load. {String(error)}</InlineError>
      ) : filteredRows.length === 0 ? (
        <EmptyState
          icon="play"
          title={rows.length === 0 ? "No runs yet" : "No runs match these filters"}
          description={
            rows.length === 0
              ? "Open a journey, start processing on a stage, or submit a DSL execution."
              : "Adjust the search, status or date filters, or clear them to see all runs."
          }
          action={
            rows.length === 0 ? (
              <Link to="/journeys" className="link">
                Go to journeys
              </Link>
            ) : (
              <button type="button" className="link" onClick={clearFilters}>
                Clear filters
              </button>
            )
          }
        />
      ) : (
        <>
          <TableShell>
            <table className="tbl">
              <thead>
                <tr>
                  <th className="w-10">
                    <input
                      type="checkbox"
                      aria-label="Select all deletable runs"
                      checked={deletableRows.length > 0 && deletableRows.every((row) => selected.has(rowKey(row)))}
                      onChange={toggleAllDeletable}
                      disabled={deletableRows.length === 0}
                      className="check"
                    />
                  </th>
                  <th>Journey</th>
                  <th>Run</th>
                  <th>Stage</th>
                  <th>Started</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {pageRows.map((row) => {
                  const deletable = isDeletable(row);
                  const key = rowKey(row);
                  return (
                    <tr key={key} className={selected.has(key) ? "!bg-primary/5" : undefined}>
                      <td>
                        <input
                          type="checkbox"
                          aria-label={`Select ${runLabel(row)}`}
                          checked={selected.has(key)}
                          disabled={!deletable}
                          onChange={() => toggleRow(row)}
                          className="check disabled:opacity-30"
                        />
                      </td>
                      <td className="max-w-[300px]">
                        {row.kind === "stage_job" && row.journeyName ? (
                          <Link to={`/journeys/${row.journeyId}`} className="block truncate font-medium text-foreground hover:text-primary dark:hover:text-brand-hi">
                            {row.journeyName}
                          </Link>
                        ) : (
                          <span className="block truncate font-medium text-foreground">{row.journeyId}</span>
                        )}
                        <span className="text-xs text-muted-foreground">{row.kind === "stage_job" ? "Stage job" : "DSL"}</span>
                      </td>
                      <td>
                        <Link to={runHref(row)} className="link font-mono text-xs">
                          {runLabel(row)}
                        </Link>
                      </td>
                      <td className="text-muted-foreground">
                        {row.kind === "stage_job"
                          ? row.jobType === "journey"
                            ? `All stages (${row.stageIds?.length ?? "—"})`
                            : row.stageId ?? "—"
                          : "—"}
                      </td>
                      <td className="whitespace-nowrap text-muted-foreground" title={formatRunTime(row)}>
                        {row.kind === "stage_job" && row.startedAt ? relativeTime(row.startedAt) : "—"}
                      </td>
                      <td>
                        <StatusPill status={row.status} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </TableShell>
          <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-muted-foreground">
            <span>
              Showing {Math.min(visible, filteredRows.length).toLocaleString()} of {filteredRows.length.toLocaleString()}
              {filteredRows.length !== rows.length ? ` (${rows.length.toLocaleString()} in total)` : ""}
            </span>
            {filteredRows.length > visible && (
              <Button variant="outline" size="sm" onClick={() => setVisible((v) => v + PAGE_SIZE)}>
                Show {Math.min(PAGE_SIZE, filteredRows.length - visible)} more
              </Button>
            )}
          </div>
        </>
      )}
    </div>
  );
}
