import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { EmptyState } from "@/components/EmptyState";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/services/api";

export function StageJobDetailPage() {
  const { journeyId = "", jobId = "" } = useParams();

  const jobQuery = useQuery({
    queryKey: ["stage-job", journeyId, jobId],
    queryFn: () => api.getStageJob(journeyId, jobId),
    enabled: Boolean(journeyId && jobId),
    refetchInterval: (q) => {
      const status = q.state.data?.status?.toLowerCase();
      return status === "running" || status === "in_progress" ? 2_000 : false;
    },
  });

  const job = jobQuery.data;

  return (
    <div className="space-y-4">
      <Button variant="ghost" size="sm" asChild className="-ml-2">
        <Link to={`/journeys/${journeyId}`}>
          <ArrowLeft className="h-4 w-4" />
          Back to journey
        </Link>
      </Button>

      {jobQuery.isLoading ? (
        <p className="text-sm text-muted-foreground">Loading job…</p>
      ) : jobQuery.error || !job ? (
        <EmptyState title="Job not found" description={String(jobQuery.error ?? "Unknown job")} />
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-xl font-semibold font-mono">{job.id}</h2>
              <p className="text-sm text-muted-foreground">
                {job.stageName ?? job.stageId} · {journeyId}
              </p>
            </div>
            <StatusBadge status={job.status} />
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Progress</CardTitle>
              </CardHeader>
              <CardContent className="text-2xl font-bold">{Math.round(job.progress)}%</CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Started</CardTitle>
              </CardHeader>
              <CardContent className="text-sm">{job.startedAt ?? "—"}</CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Duration</CardTitle>
              </CardHeader>
              <CardContent className="text-sm">{job.duration ?? "—"}</CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Run details</CardTitle>
            </CardHeader>
            <CardContent className="text-sm space-y-2">
              <p>
                <span className="text-muted-foreground">Triggered by:</span> {job.triggeredBy ?? "—"}
              </p>
              <p>
                <span className="text-muted-foreground">Ended:</span> {job.endedAt ?? "—"}
              </p>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
