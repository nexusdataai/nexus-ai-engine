import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { EmptyState } from "@/components/EmptyState";
import { DateTimePicker } from "@/components/DateTimePicker";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/services/api";
import { truncateId } from "@/lib/utils";
import type { UnifiedRunRow } from "@/types/stageJourney";

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
  return `${row.kind}-${row.id}`;
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

export function ExecutionsListPage() {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [fromFilter, setFromFilter] = useState<Date | null>(null);
  const [toFilter, setToFilter] = useState<Date | null>(null);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["runs"],
    queryFn: () => api.listAllRuns(),
    refetchInterval: 5_000,
  });

  const rows = data ?? [];

  const filteredRows = useMemo(() => {
    const fromMs = fromFilter?.getTime() ?? null;
    const toMs = toFilter ? toFilter.getTime() + 59_999 : null;
    return rows.filter((row) => {
      const ts = parseRunTimestamp(row);
      if (ts == null) {
        return fromMs == null && toMs == null;
      }
      if (fromMs != null && ts < fromMs) return false;
      if (toMs != null && ts > toMs) return false;
      return true;
    });
  }, [rows, fromFilter, toFilter]);

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

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Executions</h2>
          <p className="text-sm text-muted-foreground">
            Stage jobs and DSL runs in one monitor — auto-refreshes every 5s.
          </p>
        </div>
        <button type="button" className="text-sm text-primary hover:underline" onClick={() => refetch()}>
          Refresh
        </button>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Total runs</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-bold">{rows.length}</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Running now</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-bold text-blue-400">{running.length}</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Journeys</CardTitle>
          </CardHeader>
          <CardContent>
            <Link to="/journeys" className="text-sm text-primary hover:underline">
              Browse journeys →
            </Link>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <CardTitle className="text-base">All runs</CardTitle>
            {selectedRows.length > 0 && (
              <Button
                variant="destructive"
                size="sm"
                disabled={deleteMutation.isPending}
                onClick={handleDelete}
              >
                {deleteMutation.isPending ? "Deleting…" : `Delete selected (${selectedRows.length})`}
              </Button>
            )}
          </div>
          <div className="flex flex-wrap items-end gap-3">
            <DateTimePicker label="From" value={fromFilter} onChange={setFromFilter} />
            <DateTimePicker label="To" value={toFilter} onChange={setToFilter} />
            {(fromFilter || toFilter) && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setFromFilter(null);
                  setToFilter(null);
                }}
              >
                Clear filters
              </Button>
            )}
            <span className="text-xs text-muted-foreground pb-2">
              Showing {filteredRows.length} of {rows.length}
            </span>
          </div>
          {deleteMutation.isError && (
            <p className="text-sm text-destructive">{String(deleteMutation.error)}</p>
          )}
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : error ? (
            <EmptyState title="Failed to load" description={String(error)} />
          ) : filteredRows.length === 0 ? (
            <EmptyState
              title={rows.length === 0 ? "No runs yet" : "No runs in this date range"}
              description={
                rows.length === 0
                  ? "Open a journey, start processing on a stage, or submit a DSL execution."
                  : "Adjust the date/time filters or clear them to see all runs."
              }
              action={
                rows.length === 0 ? (
                  <Link to="/journeys" className="text-sm text-primary hover:underline">
                    Go to journeys
                  </Link>
                ) : (
                  <button
                    type="button"
                    className="text-sm text-primary hover:underline"
                    onClick={() => {
                      setFromFilter(null);
                      setToFilter(null);
                    }}
                  >
                    Clear filters
                  </button>
                )
              }
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-muted-foreground border-b border-border">
                    <th className="py-2 pr-2 w-8">
                      <input
                        type="checkbox"
                        aria-label="Select all deletable runs"
                        checked={
                          deletableRows.length > 0 &&
                          deletableRows.every((row) => selected.has(rowKey(row)))
                        }
                        onChange={toggleAllDeletable}
                        disabled={deletableRows.length === 0}
                        className="rounded border-border"
                      />
                    </th>
                    <th className="py-2 pr-4">Run</th>
                    <th className="py-2 pr-4">Started</th>
                    <th className="py-2 pr-4">Type</th>
                    <th className="py-2 pr-4">Journey</th>
                    <th className="py-2 pr-4">Stage</th>
                    <th className="py-2">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredRows.map((row) => {
                    const deletable = isDeletable(row);
                    const key = rowKey(row);
                    return (
                      <tr key={key} className="border-b border-border/50">
                        <td className="py-2 pr-2">
                          <input
                            type="checkbox"
                            aria-label={`Select ${runLabel(row)}`}
                            checked={selected.has(key)}
                            disabled={!deletable}
                            onChange={() => toggleRow(row)}
                            className="rounded border-border disabled:opacity-40"
                          />
                        </td>
                        <td className="py-2 pr-4">
                          <Link to={runHref(row)} className="text-primary hover:underline font-mono">
                            {runLabel(row)}
                          </Link>
                        </td>
                        <td className="py-2 pr-4 text-muted-foreground whitespace-nowrap">
                          {formatRunTime(row)}
                        </td>
                        <td className="py-2 pr-4 capitalize">{row.kind === "stage_job" ? "Stage job" : "DSL"}</td>
                        <td className="py-2 pr-4">
                          {row.kind === "stage_job" && row.journeyName ? (
                            <Link to={`/journeys/${row.journeyId}`} className="hover:underline">
                              {row.journeyName}
                            </Link>
                          ) : (
                            row.journeyId
                          )}
                        </td>
                      <td className="py-2 pr-4 text-muted-foreground">
                        {row.kind === "stage_job"
                          ? row.jobType === "journey"
                            ? `All stages (${row.stageIds?.length ?? "—"})`
                            : row.stageId ?? "—"
                          : "—"}
                      </td>
                        <td className="py-2">
                          <StatusBadge status={row.status} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
