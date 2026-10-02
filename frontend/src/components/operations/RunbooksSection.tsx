import { useEffect, useState } from "react";
import { AlertTriangle, Inbox, RefreshCw, RotateCcw, ServerCrash, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/services/api";
import type { CrashAnalyzerResponse, CrashedPod, DlqEntry, DlqListResponse, StaleJob, StaleJobsResponse } from "@/types/runbooks";

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
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Button onClick={load} disabled={loading} variant="outline" size="sm">
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Scan Stale Jobs
        </Button>
        <Button onClick={cancelAll} disabled={cancelling || !data?.jobs.length} variant="destructive" size="sm">
          <Trash2 className="h-4 w-4" />
          Cancel All Stale
        </Button>
      </div>
      {error ? <p className="text-sm text-red-500">{error}</p> : null}
      {data ? (
        <div className="flex flex-wrap gap-2 text-sm">
          <span className="rounded-full border px-2 py-0.5">Total: {data.summary.total_stale ?? 0}</span>
          <span className="rounded-full border px-2 py-0.5">STALE: {data.summary.STALE ?? 0}</span>
          <span className="rounded-full border px-2 py-0.5">LIKELY-STUCK: {data.summary["LIKELY-STUCK"] ?? 0}</span>
          <span className="rounded-full border px-2 py-0.5">UNVERIFIED-LONG: {data.summary["UNVERIFIED-LONG"] ?? 0}</span>
          <span className="rounded-full border px-2 py-0.5">Blocked schedules: {data.summary.blocked_schedules ?? 0}</span>
        </div>
      ) : null}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Stale Jobs</CardTitle>
        </CardHeader>
        <CardContent>
          {!data ? (
            <p className="text-sm text-muted-foreground">Run a scan to list stuck in-progress jobs.</p>
          ) : data.jobs.length === 0 ? (
            <p className="text-sm text-muted-foreground">No stale jobs found.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="py-2 pr-3">Job ID</th>
                    <th className="py-2 pr-3">Journey</th>
                    <th className="py-2 pr-3">Stage</th>
                    <th className="py-2 pr-3">Step</th>
                    <th className="py-2 pr-3">Age (min)</th>
                    <th className="py-2 pr-3">Confidence</th>
                    <th className="py-2">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {data.jobs.map((job) => (
                    <tr key={`${job.pk}-${job.sk}`} className="border-b border-border/50">
                      <td className="py-2 pr-3 font-mono text-xs">{job.job_id}</td>
                      <td className="py-2 pr-3">{job.journey_id}</td>
                      <td className="py-2 pr-3">{job.stage_id}</td>
                      <td className="py-2 pr-3">{job.current_step || "—"}</td>
                      <td className="py-2 pr-3">{Number(job.age_min).toFixed(1)}</td>
                      <td className="py-2 pr-3">{job.confidence}</td>
                      <td className="py-2">
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
        </CardContent>
      </Card>
    </div>
  );
}

function CrashPodCard({ pod }: { pod: CrashedPod }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-lg border">
      <button type="button" className="flex w-full items-center justify-between gap-2 p-3 text-left hover:bg-muted/40" onClick={() => setOpen((v) => !v)}>
        <div className="flex flex-wrap items-center gap-2 min-w-0">
          <span className="font-mono text-sm font-medium truncate">{pod.name}</span>
          <span className="rounded-full border px-2 py-0.5 text-xs">{pod.phase}</span>
          <span className="rounded-full border border-red-500/40 px-2 py-0.5 text-xs text-red-400">{pod.restarts} restarts</span>
          {pod.node ? <span className="rounded-full border px-2 py-0.5 text-xs">node: {pod.node}</span> : null}
        </div>
      </button>
      {open ? (
        <div className="px-3 pb-3 space-y-3">
          {(pod.analysis || []).length > 0 ? (
            <div className="rounded-md bg-amber-500/10 border border-amber-500/20 p-2 text-xs space-y-1">
              <p className="font-medium">Analysis</p>
              {pod.analysis!.map((line) => (
                <p key={line} className="text-muted-foreground">
                  {line}
                </p>
              ))}
            </div>
          ) : null}
          {(pod.containers || []).map((ctr) => (
            <div key={ctr.name} className="rounded border p-2 text-xs space-y-2">
              <div className="flex flex-wrap gap-2 items-center">
                <span className="font-medium">container: {ctr.name}</span>
                <span className="rounded-full border px-2 py-0.5">{ctr.restart_count} restarts</span>
                {ctr.last_terminated?.reason ? (
                  <span className="rounded-full border px-2 py-0.5">
                    {ctr.last_terminated.reason} (exit {ctr.last_terminated.exit_code})
                  </span>
                ) : null}
              </div>
              {ctr.last_terminated?.message ? <p className="text-muted-foreground whitespace-pre-wrap">{ctr.last_terminated.message}</p> : null}
              {ctr.previous_log_tail ? (
                <pre className="text-[10px] bg-zinc-950 text-zinc-100 p-2 rounded max-h-48 overflow-auto whitespace-pre-wrap">{ctr.previous_log_tail}</pre>
              ) : (
                <p className="text-muted-foreground italic">No previous-container log retained by kubelet.</p>
              )}
            </div>
          ))}
          {(pod.events || []).length > 0 ? (
            <div className="space-y-1">
              <p className="text-xs font-medium">Recent pod events</p>
              {pod.events!.map((ev, i) => (
                <p key={`${ev.reason}-${i}`} className="text-[11px] text-muted-foreground font-mono">
                  {ev.last_seen} {ev.type}/{ev.reason}: {ev.message}
                </p>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
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
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-2">
        <div>
          <label className="text-xs text-muted-foreground block mb-1">Component filter (optional)</label>
          <input
            className="h-8 w-48 rounded-md border bg-background px-2 text-xs"
            value={component}
            onChange={(e) => setComponent(e.target.value)}
            placeholder="e.g. backend, frontend"
          />
        </div>
        <Button onClick={load} disabled={loading} variant="outline" size="sm">
          <ServerCrash className={`h-4 w-4 ${loading ? "animate-pulse" : ""}`} />
          Analyze Crashes
        </Button>
      </div>
      {error ? <p className="text-sm text-red-500">{error}</p> : null}
      {data ? (
        <p className="text-sm text-muted-foreground">
          Namespace: <span className="font-mono">{data.namespace}</span>
          {data.log_tail_lines ? <span className="ml-2">· log tail: {data.log_tail_lines} lines</span> : null}
          {!data.available && data.message ? <span className="ml-2 text-amber-600">({data.message})</span> : null}
        </p>
      ) : null}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <AlertTriangle className="h-4 w-4" />
            Pods with Restarts ({data?.count ?? 0})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {!data ? (
            <p className="text-sm text-muted-foreground">
              Run analysis to inspect restarted pods — includes exit reason, previous logs, and events.
            </p>
          ) : data.pods.length === 0 ? (
            <p className="text-sm text-muted-foreground">No restarted pods found in this namespace.</p>
          ) : (
            <div className="space-y-2">
              {data.pods.map((pod) => (
                <CrashPodCard key={pod.name} pod={pod} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
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

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Failed transformation jobs land here after <span className="font-mono">fail_job</span>. Reprocess queues a new run of the same stage.
        Select pending or reprocessed entries for bulk re-run; dismissed entries cannot be reprocessed.
      </p>
      <div className="flex flex-wrap items-end gap-2">
        <div>
          <label className="mb-1 block text-xs text-muted-foreground">Status</label>
          <select
            className="h-8 rounded-md border bg-background px-2 text-xs"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">All</option>
            <option value="pending_review">Pending review</option>
            <option value="reprocessed">Reprocessed</option>
            <option value="dismissed">Dismissed</option>
          </select>
        </div>
        <Button onClick={load} disabled={loading} variant="outline" size="sm">
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Load DLQ
        </Button>
        <Button onClick={importFailed} disabled={busy} variant="outline" size="sm">
          <Inbox className="h-4 w-4" />
          Import Failed Jobs
        </Button>
        <Button onClick={reprocessSelected} disabled={busy || selected.size === 0} size="sm">
          <RotateCcw className="h-4 w-4" />
          Reprocess Selected ({selected.size})
        </Button>
      </div>
      {error ? <p className="text-sm text-red-500">{error}</p> : null}
      {data ? (
        <div className="flex flex-wrap gap-2 text-sm">
          <span className="rounded-full border px-2 py-0.5">Total: {data.count}</span>
          <span className="rounded-full border px-2 py-0.5">Pending: {data.summary.pending_review ?? 0}</span>
          <span className="rounded-full border px-2 py-0.5">Reprocessed: {data.summary.reprocessed ?? 0}</span>
          <span className="rounded-full border px-2 py-0.5">Dismissed: {data.summary.dismissed ?? 0}</span>
          {data.imported != null ? <span className="rounded-full border px-2 py-0.5">Imported: {data.imported}</span> : null}
          {data.count > 0 && (data.summary.pending_review ?? 0) === 0 ? (
            <span className="text-xs text-muted-foreground">No pending entries — switch filter to All or import failed jobs.</span>
          ) : null}
        </div>
      ) : null}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Dead Letter Queue</CardTitle>
        </CardHeader>
        <CardContent>
          {!data ? (
            <p className="text-sm text-muted-foreground">Load the DLQ or import existing failed jobs.</p>
          ) : data.items.length === 0 ? (
            <p className="text-sm text-muted-foreground">No DLQ entries. Failed jobs appear here after they fail, or use Import Failed Jobs.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="py-2 pr-2">
                      <input
                        type="checkbox"
                        aria-label="Select all reprocessable entries"
                        disabled={selectableItems.length === 0 || busy}
                        checked={selectableItems.length > 0 && selectableItems.every((item) => selected.has(item.sk))}
                        onChange={(e) => {
                          if (e.target.checked) setSelected(new Set(selectableItems.map((item) => item.sk)));
                          else setSelected(new Set());
                        }}
                      />
                    </th>
                    <th className="py-2 pr-3">Job</th>
                    <th className="py-2 pr-3">Journey</th>
                    <th className="py-2 pr-3">Stage</th>
                    <th className="py-2 pr-3">Error</th>
                    <th className="py-2 pr-3">Status</th>
                    <th className="py-2">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((item) => {
                    const canSelect = isSelectable(item);
                    return (
                    <tr
                      key={item.sk}
                      className={`border-b border-border/50 ${canSelect ? "cursor-pointer hover:bg-muted/30" : ""}`}
                      onClick={() => {
                        if (canSelect && !busy) toggle(item.sk);
                      }}
                    >
                      <td className="py-2 pr-2" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
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
                      <td className="py-2 pr-3 font-mono text-xs">{item.job_id}</td>
                      <td className="py-2 pr-3">{item.journey_id}</td>
                      <td className="py-2 pr-3">{item.stage_id || "—"}</td>
                      <td className="max-w-xs truncate py-2 pr-3 text-xs text-muted-foreground" title={item.error}>
                        {item.error || "—"}
                      </td>
                      <td className="py-2 pr-3">{item.status}</td>
                      <td className="py-2" onClick={(e) => e.stopPropagation()}>
                        <div className="flex gap-1">
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
                              <Button size="sm" variant="ghost" disabled={busy} onClick={() => reprocessOne(item)}>
                                Re-run
                              </Button>
                              {item.new_job_id ? (
                                <span className="self-center font-mono text-xs text-muted-foreground">{item.new_job_id}</span>
                              ) : null}
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
        </CardContent>
      </Card>
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
