import { useEffect, useState } from "react";

import { Icon } from "@/components/ds/Icon";
import { CodeBlock, EmptyState, Field, InlineError, MetricStrip, Notice, Panel, StatusPill, SubHeading, Toolbar, toneOf, type Metric } from "@/components/ds/kit";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { api } from "@/services/api";
import type { CrashAnalyzerResponse, CrashedPod, DlqEntry, DlqListResponse, StaleJob, StaleJobsResponse } from "@/types/runbooks";

import { stripColumns } from "./parts";

function StaleJobsPanel() {
  const [loading, setLoading] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [data, setData] = useState<StaleJobsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await api.listStaleJobs());
    } catch (exc) {
      setError((exc as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const cancelAll = async () => {
    if (!window.confirm("Cancel all stale jobs (skipping unverified-long)?")) return;
    setCancelling(true);
    try {
      await api.cancelAllStaleJobs(true);
      await load();
    } catch (exc) {
      setError((exc as Error).message);
    } finally {
      setCancelling(false);
    }
  };

  const cancelOne = async (job: StaleJob) => {
    if (!window.confirm(`Cancel job ${job.job_id}?`)) return;
    try {
      await api.cancelOneStaleJob(job);
      await load();
    } catch (exc) {
      setError((exc as Error).message);
    }
  };

  return (
    <div className="space-y-6">
      {error ? <InlineError>{error}</InlineError> : null}
      {data ? (
        <MetricStrip
          columns={5}
          items={[
            { label: "Total", value: data.summary.total_stale ?? 0 },
            { label: "STALE", value: data.summary.STALE ?? 0 },
            { label: "LIKELY-STUCK", value: data.summary["LIKELY-STUCK"] ?? 0 },
            { label: "UNVERIFIED-LONG", value: data.summary["UNVERIFIED-LONG"] ?? 0 },
            { label: "Blocked schedules", value: data.summary.blocked_schedules ?? 0 },
          ]}
        />
      ) : null}
      <Panel
        title="Stale Jobs"
        flush
        actions={
          <>
            <Button onClick={load} disabled={loading} size="sm">
              <Icon name="refresh" className={loading ? "animate-spin" : undefined} />
              Scan Stale Jobs
            </Button>
            <Button onClick={cancelAll} disabled={cancelling || !data?.jobs.length} variant="destructive" size="sm">
              <Icon name="trash" />
              Cancel All Stale
            </Button>
          </>
        }
      >
        {!data ? (
          <EmptyState bare icon="clock" title="Run a scan to list stuck in-progress jobs." />
        ) : data.jobs.length === 0 ? (
          <EmptyState bare icon="check-circle" title="No stale jobs found." />
        ) : (
          <div className="scroll-thin overflow-x-auto">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Job ID</th>
                  <th>Journey</th>
                  <th>Stage</th>
                  <th>Step</th>
                  <th className="r">Age (min)</th>
                  <th>Confidence</th>
                  <th className="r">Action</th>
                </tr>
              </thead>
              <tbody>
                {data.jobs.map((job) => (
                  <tr key={`${job.pk}-${job.sk}`}>
                    <td className="font-mono text-xs text-foreground">{job.job_id}</td>
                    <td>{job.journey_id}</td>
                    <td>{job.stage_id}</td>
                    <td className="text-muted-foreground">{job.current_step || "—"}</td>
                    <td className="r num">{Number(job.age_min).toFixed(1)}</td>
                    <td>{job.confidence}</td>
                    <td className="r">
                      <Button size="sm" variant="ghost" onClick={() => cancelOne(job)}>
                        Cancel
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}

function CrashPodCard({ pod }: { pod: CrashedPod }) {
  const [open, setOpen] = useState(false);
  return (
    <li>
      <button
        type="button"
        aria-expanded={open}
        className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors duration-150 hover:bg-surface-2/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring sm:px-5"
        onClick={() => setOpen((v) => !v)}
      >
        <Icon name={open ? "chevron-down" : "chevron-right"} className="h-3.5 w-3.5 text-subtle-foreground" />
        <span className="flex min-w-0 flex-1 flex-wrap items-center gap-x-4 gap-y-1">
          <span className="truncate font-mono text-sm font-medium text-foreground">{pod.name}</span>
          <span className="text-xs text-muted-foreground">{pod.phase}</span>
          {pod.node ? <span className="text-xs text-muted-foreground">node: {pod.node}</span> : null}
        </span>
        <StatusPill tone="danger">{pod.restarts} restarts</StatusPill>
      </button>
      {open ? (
        <div className="space-y-4 border-t border-border bg-surface-2/40 px-4 py-4 sm:px-5">
          {(pod.analysis || []).length > 0 ? (
            <Notice tone="warning">
              <p className="font-medium">Analysis</p>
              {pod.analysis!.map((line) => (
                <p key={line} className="mt-1 text-muted-foreground">
                  {line}
                </p>
              ))}
            </Notice>
          ) : null}
          {(pod.containers || []).map((ctr) => (
            <div key={ctr.name} className="space-y-2 text-xs">
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                <span className="text-sm font-medium text-foreground">container: {ctr.name}</span>
                <span className="num text-muted-foreground">{ctr.restart_count} restarts</span>
                {ctr.last_terminated?.reason ? (
                  <span className="text-muted-foreground">
                    {ctr.last_terminated.reason} (exit {ctr.last_terminated.exit_code})
                  </span>
                ) : null}
              </div>
              {ctr.last_terminated?.message ? <p className="whitespace-pre-wrap text-muted-foreground">{ctr.last_terminated.message}</p> : null}
              {ctr.previous_log_tail ? (
                <CodeBlock wrap maxHeight={192}>{ctr.previous_log_tail}</CodeBlock>
              ) : (
                <p className="text-subtle-foreground">No previous-container log retained by kubelet.</p>
              )}
            </div>
          ))}
          {(pod.events || []).length > 0 ? (
            <div>
              <SubHeading>Recent pod events</SubHeading>
              <div className="space-y-1">
                {pod.events!.map((ev, i) => (
                  <p key={`${ev.reason}-${i}`} className="break-words font-mono text-xs text-muted-foreground">
                    {ev.last_seen} {ev.type}/{ev.reason}: {ev.message}
                  </p>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}

function CrashAnalyzerPanel() {
  const [loading, setLoading] = useState(false);
  const [component, setComponent] = useState("");
  const [data, setData] = useState<CrashAnalyzerResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await api.listCrashes(component));
    } catch (exc) {
      setError((exc as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <Toolbar className="items-end">
        <Field label="Component filter (optional)" htmlFor="crash-component" className="w-full sm:w-64">
          <input
            id="crash-component"
            className="field field-sm"
            value={component}
            onChange={(e) => setComponent(e.target.value)}
            placeholder="e.g. backend, frontend"
          />
        </Field>
        <Button onClick={load} disabled={loading} size="sm">
          <Icon name={loading ? "refresh" : "search"} className={loading ? "animate-spin" : undefined} />
          Analyze Crashes
        </Button>
      </Toolbar>
      {error ? <InlineError>{error}</InlineError> : null}
      <Panel
        title={<>Pods with Restarts ({data?.count ?? 0})</>}
        flush
        footer={
          data ? (
            <>
              Namespace: <span className="font-mono text-foreground">{data.namespace}</span>
              {data.log_tail_lines ? <span className="ml-2">· log tail: {data.log_tail_lines} lines</span> : null}
              {!data.available && data.message ? <span className="ml-2 text-warning">({data.message})</span> : null}
            </>
          ) : undefined
        }
      >
        {!data ? (
          <EmptyState
            bare
            icon="alert-triangle"
            title="Run analysis to inspect restarted pods — includes exit reason, previous logs, and events."
          />
        ) : data.pods.length === 0 ? (
          <EmptyState bare icon="check-circle" title="No restarted pods found in this namespace." />
        ) : (
          <ul className="divide-y divide-border">
            {data.pods.map((pod) => (
              <CrashPodCard key={pod.name} pod={pod} />
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}

function DlqPanel() {
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [data, setData] = useState<DlqListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("pending_review");
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const isSelectable = (item: DlqEntry) => item.status === "pending_review" || item.status === "reprocessed";
  const selectableItems = (data?.items || []).filter(isSelectable);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await api.listDlq(statusFilter || undefined));
      setSelected(new Set());
    } catch (exc) {
      setError((exc as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const importFailed = async () => {
    setBusy(true);
    setError(null);
    try {
      setData(await api.importFailedJobsToDlq());
      setSelected(new Set());
    } catch (exc) {
      setError((exc as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const reprocessOne = async (item: DlqEntry) => {
    if (!window.confirm(`Reprocess failed job ${item.job_id}? A new job will be queued.`)) return;
    setBusy(true);
    try {
      await api.reprocessDlq(item.sk);
      await load();
    } catch (exc) {
      setError((exc as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const reprocessSelected = async () => {
    const sks = [...selected];
    if (!sks.length) return;
    if (!window.confirm(`Reprocess ${sks.length} selected failed job(s)?`)) return;
    setBusy(true);
    try {
      await api.reprocessDlqBulk(sks);
      await load();
    } catch (exc) {
      setError((exc as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const dismissOne = async (item: DlqEntry) => {
    if (!window.confirm(`Dismiss DLQ entry for ${item.job_id}?`)) return;
    setBusy(true);
    try {
      await api.dismissDlq(item.sk);
      await load();
    } catch (exc) {
      setError((exc as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const toggle = (sk: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(sk)) next.delete(sk);
      else next.add(sk);
      return next;
    });
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- initial fetch only
  }, []);

  const summary: Metric[] = data
    ? [
        { label: "Total", value: data.count },
        { label: "Pending", value: data.summary.pending_review ?? 0 },
        { label: "Reprocessed", value: data.summary.reprocessed ?? 0 },
        { label: "Dismissed", value: data.summary.dismissed ?? 0 },
        ...(data.imported != null ? [{ label: "Imported", value: data.imported }] : []),
      ]
    : [];

  return (
    <div className="space-y-6">
      <p className="max-w-3xl text-sm text-muted-foreground">
        Failed transformation jobs land here after <span className="font-mono text-foreground">fail_job</span>. Reprocess queues a new run of the same stage.
        Select pending or reprocessed entries for bulk re-run; dismissed entries cannot be reprocessed.
      </p>
      <Toolbar className="items-end">
        <Field label="Status" htmlFor="dlq-status" className="w-full sm:w-48">
          <select
            id="dlq-status"
            className="field field-sm"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">All</option>
            <option value="pending_review">Pending review</option>
            <option value="reprocessed">Reprocessed</option>
            <option value="dismissed">Dismissed</option>
          </select>
        </Field>
        <Button onClick={load} disabled={loading} variant="outline" size="sm">
          <Icon name="refresh" className={loading ? "animate-spin" : undefined} />
          Load DLQ
        </Button>
        <Button onClick={importFailed} disabled={busy} variant="outline" size="sm">
          <Icon name="download" />
          Import Failed Jobs
        </Button>
        <Button onClick={reprocessSelected} disabled={busy || selected.size === 0} size="sm">
          <Icon name="history" />
          Reprocess Selected ({selected.size})
        </Button>
      </Toolbar>
      {error ? <InlineError>{error}</InlineError> : null}
      {data ? <MetricStrip items={summary} columns={stripColumns(summary.length)} /> : null}
      {data && data.count > 0 && (data.summary.pending_review ?? 0) === 0 ? (
        <Notice tone="neutral">No pending entries — switch filter to All or import failed jobs.</Notice>
      ) : null}
      <Panel title="Dead Letter Queue" flush>
        {!data ? (
          <EmptyState bare icon="box" title="Load the DLQ or import existing failed jobs." />
        ) : data.items.length === 0 ? (
          <EmptyState bare icon="box" title="No DLQ entries. Failed jobs appear here after they fail, or use Import Failed Jobs." />
        ) : (
          <div className="scroll-thin overflow-x-auto">
            <table className="tbl">
              <thead>
                <tr>
                  <th className="w-10">
                    <input
                      type="checkbox"
                      className="check align-middle"
                      aria-label="Select all reprocessable entries"
                      disabled={selectableItems.length === 0 || busy}
                      checked={selectableItems.length > 0 && selectableItems.every((item) => selected.has(item.sk))}
                      onChange={(e) => {
                        if (e.target.checked) setSelected(new Set(selectableItems.map((item) => item.sk)));
                        else setSelected(new Set());
                      }}
                    />
                  </th>
                  <th>Job</th>
                  <th>Journey</th>
                  <th>Stage</th>
                  <th>Error</th>
                  <th>Status</th>
                  <th className="r">Action</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((item) => {
                  const canSelect = isSelectable(item);
                  return (
                    <tr
                      key={item.sk}
                      className={cn(canSelect && "cursor-pointer", selected.has(item.sk) && "bg-primary/5")}
                      onClick={() => {
                        if (canSelect && !busy) toggle(item.sk);
                      }}
                    >
                      <td onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          className="check align-middle"
                          aria-label={`Select ${item.job_id}`}
                          disabled={!canSelect || busy}
                          title={
                            item.status === "dismissed"
                              ? "Dismissed entries cannot be reprocessed"
                              : canSelect
                                ? "Select for bulk reprocess"
                                : undefined
                          }
                          checked={selected.has(item.sk)}
                          onChange={() => toggle(item.sk)}
                        />
                      </td>
                      <td className="font-mono text-xs text-foreground">{item.job_id}</td>
                      <td>{item.journey_id}</td>
                      <td>{item.stage_id || "—"}</td>
                      <td className="max-w-xs truncate text-xs text-muted-foreground" title={item.error}>
                        {item.error || "—"}
                      </td>
                      <td>
                        <StatusPill status={item.status} tone={item.status === "pending_review" ? "warning" : toneOf(item.status)} />
                      </td>
                      <td className="r" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center justify-end gap-1">
                          {item.status === "pending_review" ? (
                            <>
                              <Button size="sm" variant="ghost" disabled={busy} onClick={() => reprocessOne(item)}>
                                Reprocess
                              </Button>
                              <Button size="sm" variant="ghost" disabled={busy} onClick={() => dismissOne(item)}>
                                Dismiss
                              </Button>
                            </>
                          ) : item.status === "reprocessed" ? (
                            <>
                              {item.new_job_id ? (
                                <span className="font-mono text-xs text-muted-foreground">{item.new_job_id}</span>
                              ) : null}
                              <Button size="sm" variant="ghost" disabled={busy} onClick={() => reprocessOne(item)}>
                                Re-run
                              </Button>
                            </>
                          ) : item.new_job_id ? (
                            <span className="font-mono text-xs text-muted-foreground">{item.new_job_id}</span>
                          ) : (
                            "—"
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}

export function RunbooksSection({ tab }: { tab: "stale-jobs" | "crash-analyzer" | "dlq" }) {
  if (tab === "crash-analyzer") {
    return <CrashAnalyzerPanel />;
  }
  if (tab === "dlq") {
    return <DlqPanel />;
  }
  return <StaleJobsPanel />;
}
