import { useState } from "react";
import { Eye, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/services/api";
import type { ArchivedJobRow } from "@/types/api";

function statusColor(status?: string | null): string {
  switch (status) {
    case "in_progress":
      return "bg-blue-100 text-blue-700";
    case "completed":
      return "bg-green-100 text-green-800";
    case "failed":
      return "bg-red-100 text-red-800";
    default:
      return "bg-muted text-muted-foreground";
  }
}

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
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Archived Jobs</CardTitle>
        <CardDescription>Search historical jobs archived from DynamoDB to Glue/Athena</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-end gap-3">
          <label className="space-y-1 text-xs text-muted-foreground">
            Job # or ID
            <input
              className="block h-9 w-40 rounded-md border bg-background px-2 text-sm text-foreground"
              placeholder="e.g. 5006"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          <label className="space-y-1 text-xs text-muted-foreground">
            From
            <input
              type="date"
              className="block h-9 w-40 rounded-md border bg-background px-2 text-sm text-foreground"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
            />
          </label>
          <label className="space-y-1 text-xs text-muted-foreground">
            To
            <input
              type="date"
              className="block h-9 w-40 rounded-md border bg-background px-2 text-sm text-foreground"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
            />
          </label>
          <Button size="sm" className="h-9" onClick={() => void handleSearch()} disabled={searching}>
            {searching ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
            Search
          </Button>
        </div>

        {searched ? (
          <div className="overflow-hidden rounded-lg border">
            <table className="w-full text-sm">
              <thead className="bg-muted/50">
                <tr>
                  <th className="px-3 py-2 text-left font-medium">Job</th>
                  <th className="px-3 py-2 text-left font-medium">Stage</th>
                  <th className="px-3 py-2 text-left font-medium">Status</th>
                  <th className="px-3 py-2 text-left font-medium">Start Time</th>
                  <th className="px-3 py-2 text-left font-medium">Duration</th>
                  <th className="px-3 py-2 text-left font-medium">Triggered By</th>
                  <th className="px-3 py-2 text-left font-medium">Logs</th>
                </tr>
              </thead>
              <tbody>
                {results.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-3 py-6 text-center text-muted-foreground">
                      {searching ? "Searching…" : "No archived jobs found"}
                    </td>
                  </tr>
                ) : (
                  results.map((job) => (
                    <tr key={job.job_id} className="cursor-pointer border-t hover:bg-muted/30" onClick={() => void handleViewLogs(job)}>
                      <td className="px-3 py-2 font-mono text-xs">#{job.execution_number ?? job.job_id}</td>
                      <td className="px-3 py-2">{job.stage_name || job.stage_id || "—"}</td>
                      <td className="px-3 py-2">
                        <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${statusColor(job.status)}`}>
                          {job.status || "—"}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-xs text-muted-foreground">
                        {job.start_time ? new Date(job.start_time).toLocaleString() : "-"}
                      </td>
                      <td className="px-3 py-2 text-xs">
                        {job.duration ? `${Math.round(Number(job.duration))}s` : "-"}
                      </td>
                      <td className="px-3 py-2 text-xs">{job.triggered_by || "-"}</td>
                      <td className="px-3 py-2">
                        <Eye className="h-4 w-4 text-muted-foreground" />
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        ) : null}

        {selectedJob ? (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={() => setSelectedJob(null)}>
            <div className="max-h-[80vh] w-full max-w-4xl overflow-hidden rounded-lg bg-background shadow-xl" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center justify-between border-b px-6 py-4">
                <div>
                  <h3 className="text-lg font-semibold">Job #{selectedJob.execution_number} — Step Logs</h3>
                  <p className="text-sm text-muted-foreground">
                    {selectedJob.job_id} • {selectedJob.status}
                  </p>
                </div>
                <Button variant="ghost" size="sm" onClick={() => setSelectedJob(null)}>
                  ✕
                </Button>
              </div>
              <div className="max-h-[calc(80vh-80px)] overflow-y-auto p-6">
                {loadingLogs ? (
                  <div className="flex items-center justify-center py-12 text-sm text-muted-foreground">
                    <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                    Loading logs from S3…
                  </div>
                ) : Object.keys(stepLogs).length === 0 ? (
                  <p className="py-12 text-center text-muted-foreground">No step logs found for this job</p>
                ) : (
                  <div className="space-y-4">
                    {Object.entries(stepLogs).map(([stepName, logs]) => {
                      const entries = Array.isArray(logs) ? logs : [];
                      return (
                        <div key={stepName} className="rounded-lg border">
                          <div className="flex items-center border-b bg-muted/50 px-4 py-2 text-sm font-medium">
                            {stepName.replace(/_/g, " ")}
                            <span className="ml-auto text-xs text-muted-foreground">{entries.length} entries</span>
                          </div>
                          <div className="max-h-48 overflow-y-auto bg-[#0d1117] p-3 font-mono text-xs text-green-400">
                            {entries.map((entry: { timestamp?: string; level?: string; message?: string }, idx: number) => (
                              <div key={idx} className="py-0.5">
                                <span className="text-gray-500">{entry.timestamp?.substring(11, 19) || ""}</span>{" "}
                                <span
                                  className={
                                    entry.level === "ERROR"
                                      ? "text-red-400"
                                      : entry.level === "WARNING"
                                        ? "text-yellow-400"
                                        : "text-green-400"
                                  }
                                >
                                  {entry.level}
                                </span>{" "}
                                {entry.message}
                              </div>
                            ))}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
