import { useState } from "react";

import { Icon } from "@/components/ds/Icon";
import { DetailSheet, EmptyState, Field, Panel, SkeletonRows, StatusPill } from "@/components/ds/kit";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { api } from "@/services/api";
import type { ArchivedJobRow } from "@/types/api";

export function ArchivedJobsSearch() {
  const [query, setQuery] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [results, setResults] = useState<ArchivedJobRow[]>([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const [selectedJob, setSelectedJob] = useState<ArchivedJobRow | null>(null);
  const [stepLogs, setStepLogs] = useState<Record<string, unknown>>({});
  const [loadingLogs, setLoadingLogs] = useState(false);

  const handleSearch = async () => {
    setSearching(true);
    setSearched(true);
    try {
      const resp = await api.searchArchivedJobs(query || undefined, dateFrom || undefined, dateTo || undefined);
      setResults(resp.jobs || []);
    } catch {
      setResults([]);
    } finally {
      setSearching(false);
    }
  };

  const handleViewLogs = async (job: ArchivedJobRow) => {
    setSelectedJob(job);
    setStepLogs({});
    setLoadingLogs(true);
    try {
      const resp = await api.getArchivedJobLogs(job.job_id);
      if (resp.success && resp.steps) setStepLogs(resp.steps);
    } catch {
      /* ignore */
    }
    setLoadingLogs(false);
  };

  return (
    <Panel
      title="Archived Jobs"
      description="Search historical jobs archived from DynamoDB to Glue/Athena"
      flush
    >
      <form
        className="flex flex-wrap items-end gap-3 border-b border-border p-4 sm:px-5"
        onSubmit={(e) => {
          e.preventDefault();
          void handleSearch();
        }}
      >
        <Field label="Job # or ID" htmlFor="arch-q" className="w-full sm:w-48">
          <input id="arch-q" className="field" placeholder="e.g. 5006" value={query} onChange={(e) => setQuery(e.target.value)} />
        </Field>
        <Field label="From" htmlFor="arch-from" className="w-[calc(50%-6px)] sm:w-44">
          <input id="arch-from" type="date" className="field" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        </Field>
        <Field label="To" htmlFor="arch-to" className="w-[calc(50%-6px)] sm:w-44">
          <input id="arch-to" type="date" className="field" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </Field>
        <Button type="submit" disabled={searching}>
          <Icon name={searching ? "spinner" : "search"} className={searching ? "animate-spin" : undefined} />
          Search
        </Button>
      </form>

      {!searched ? (
        <EmptyState bare icon="folder" title="Search the archive" description="Enter a job number or pick a date range, then search. Results come from the long-term archive, so a search can take a few seconds." />
      ) : searching ? (
        <SkeletonRows rows={4} />
      ) : results.length === 0 ? (
        <EmptyState bare icon="search" title="No archived jobs found" description="Try a wider date range or a different job number." />
      ) : (
        <div className="scroll-thin overflow-x-auto">
          <table className="tbl">
            <thead>
              <tr>
                <th>Job</th>
                <th>Stage</th>
                <th>Status</th>
                <th>Start Time</th>
                <th className="r">Duration</th>
                <th>Triggered By</th>
                <th className="r">Logs</th>
              </tr>
            </thead>
            <tbody>
              {results.map((job) => (
                <tr key={job.job_id} className="cursor-pointer" onClick={() => void handleViewLogs(job)}>
                  <td className="font-mono text-xs text-foreground">#{job.execution_number ?? job.job_id}</td>
                  <td>{job.stage_name || job.stage_id || "—"}</td>
                  <td>{job.status ? <StatusPill status={job.status} /> : "—"}</td>
                  <td className="whitespace-nowrap text-muted-foreground">
                    {job.start_time ? new Date(job.start_time).toLocaleString() : "-"}
                  </td>
                  <td className="r num">{job.duration ? `${Math.round(Number(job.duration))}s` : "-"}</td>
                  <td className="text-muted-foreground">{job.triggered_by || "-"}</td>
                  <td className="r">
                    <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                      <Icon name="eye" className="h-3.5 w-3.5" /> View
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <DetailSheet
        open={Boolean(selectedJob)}
        onClose={() => setSelectedJob(null)}
        wide
        title={selectedJob ? `Job #${selectedJob.execution_number} — Step Logs` : ""}
        description={selectedJob?.job_id}
        meta={selectedJob?.status ? <StatusPill status={selectedJob.status} variant="soft" /> : undefined}
      >
        {loadingLogs ? (
          <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
            <Icon name="spinner" className="animate-spin" />
            Loading logs from S3…
          </div>
        ) : Object.keys(stepLogs).length === 0 ? (
          <EmptyState bare icon="terminal" title="No step logs found for this job" />
        ) : (
          <div className="space-y-4">
            {Object.entries(stepLogs).map(([stepName, logs]) => {
              const entries = Array.isArray(logs) ? logs : [];
              return (
                <section key={stepName} className="overflow-hidden rounded-lg border border-border">
                  <div className="flex items-center border-b border-border bg-surface-2/60 px-4 py-2 text-sm font-medium first-letter:uppercase">
                    {stepName.replace(/_/g, " ")}
                    <span className="num ml-auto text-xs font-normal text-muted-foreground">{entries.length} entries</span>
                  </div>
                  <div className="scroll-thin max-h-56 overflow-y-auto bg-background p-3 font-mono text-xs leading-5">
                    {entries.map((entry: { timestamp?: string; level?: string; message?: string }, idx: number) => (
                      <div key={idx} className="flex gap-3 whitespace-pre-wrap break-all">
                        <span className="num shrink-0 text-subtle-foreground">{entry.timestamp?.substring(11, 19) || ""}</span>
                        <span
                          className={cn(
                            "w-[58px] shrink-0",
                            entry.level === "ERROR" ? "text-destructive" : entry.level === "WARNING" ? "text-warning" : "text-primary dark:text-brand-hi",
                          )}
                        >
                          {entry.level}
                        </span>
                        <span className="min-w-0 text-foreground">{entry.message}</span>
                      </div>
                    ))}
                  </div>
                </section>
              );
            })}
          </div>
        )}
      </DetailSheet>
    </Panel>
  );
}
