import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Play, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { EmptyState } from "@/components/EmptyState";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { api } from "@/services/api";
import type { StageJourneyStage } from "@/types/stageJourney";

function StagePanel({
  stage,
  selected,
  onSelect,
}: {
  stage: StageJourneyStage;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "w-full text-left rounded-md border px-3 py-2 transition-colors",
        selected ? "border-primary bg-primary/10" : "border-border hover:bg-accent",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium">{stage.name}</span>
        <StatusBadge status={stage.status} />
      </div>
      <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{stage.description}</p>
    </button>
  );
}

export function JourneyDetailPage() {
  const { journeyId = "" } = useParams();
  const qc = useQueryClient();

  const journeyQuery = useQuery({
    queryKey: ["stage-journey", journeyId],
    queryFn: () => api.getStageJourney(journeyId),
    enabled: Boolean(journeyId),
    refetchInterval: 5_000,
  });

  const journey = journeyQuery.data;
  const [selectedStageId, setSelectedStageId] = useState<string | null>(null);

  useEffect(() => {
    if (journey?.stages.length && !selectedStageId) {
      setSelectedStageId(journey.stages[0].id);
    }
  }, [journey, selectedStageId]);

  const selectedStage = journey?.stages.find((s) => s.id === selectedStageId) ?? null;

  const runMut = useMutation({
    mutationFn: (stageId: string) => api.runStageJob(journeyId, stageId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["stage-journey", journeyId] });
      qc.invalidateQueries({ queryKey: ["runs"] });
    },
  });

  if (journeyQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">Loading journey…</p>;
  }
  if (journeyQuery.error || !journey) {
    return (
      <EmptyState
        title="Journey not found"
        description={String(journeyQuery.error ?? "Unknown journey")}
        action={
          <Button variant="outline" asChild>
            <Link to="/journeys">Back to journeys</Link>
          </Button>
        }
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <Button variant="ghost" size="sm" asChild className="-ml-2">
            <Link to="/journeys">
              <ArrowLeft className="h-4 w-4" />
              Journeys
            </Link>
          </Button>
          <h2 className="text-xl font-semibold">{journey.name}</h2>
          <p className="text-sm text-muted-foreground max-w-2xl">{journey.description}</p>
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <StatusBadge status={journey.status} />
            <span className="text-xs font-mono text-muted-foreground">{journey.id}</span>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={() => journeyQuery.refetch()}>
          <RefreshCw className="h-4 w-4" />
          Refresh
        </Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Total jobs</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-bold">{journey.summary.totalJobs}</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Completed</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-bold text-emerald-400">{journey.summary.completedJobs}</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Running</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-bold text-blue-400">{journey.summary.runningJobs}</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Failed</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-bold text-red-400">{journey.summary.failedJobs}</CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-[240px_1fr]">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Processing stages</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {journey.stages.map((stage) => (
              <StagePanel
                key={stage.id}
                stage={stage}
                selected={stage.id === selectedStageId}
                onSelect={() => setSelectedStageId(stage.id)}
              />
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between gap-2">
              <CardTitle className="text-base">{selectedStage?.name ?? "Stage"}</CardTitle>
              {selectedStage ? (
                <Button
                  size="sm"
                  disabled={runMut.isPending}
                  onClick={() => runMut.mutate(selectedStage.id)}
                >
                  <Play className="h-4 w-4" />
                  Start processing
                </Button>
              ) : null}
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {selectedStage?.description ? (
              <p className="text-sm text-muted-foreground">{selectedStage.description}</p>
            ) : null}
            {selectedStage?.steps.length ? (
              <ol className="space-y-2">
                {selectedStage.steps.map((step, index) => (
                  <li key={step.id} className="flex gap-3 rounded-md border border-border px-3 py-2">
                    <span className="text-xs text-muted-foreground w-5">{index + 1}</span>
                    <div>
                      <p className="text-sm font-medium">{step.name}</p>
                      {step.description ? (
                        <p className="text-xs text-muted-foreground">{step.description}</p>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="text-sm text-muted-foreground">No step metadata for this stage.</p>
            )}
            {runMut.error ? (
              <p className="text-sm text-red-400">{String(runMut.error)}</p>
            ) : null}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Job history</CardTitle>
        </CardHeader>
        <CardContent>
          {journey.jobs.length === 0 ? (
            <EmptyState title="No jobs yet" description="Start processing on a stage to create the first job." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-muted-foreground border-b border-border">
                    <th className="py-2 pr-4">Job</th>
                    <th className="py-2 pr-4">Stage</th>
                    <th className="py-2 pr-4">Started</th>
                    <th className="py-2">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {journey.jobs.map((job) => (
                    <tr key={job.id} className="border-b border-border/50">
                      <td className="py-2 pr-4">
                        <Link
                          to={`/executions/stage/${journey.id}/${job.id}`}
                          className="text-primary hover:underline font-mono"
                        >
                          {job.id}
                        </Link>
                      </td>
                      <td className="py-2 pr-4">{job.stageName ?? job.stageId}</td>
                      <td className="py-2 pr-4 text-muted-foreground">{job.startedAt ?? "—"}</td>
                      <td className="py-2">
                        <StatusBadge status={job.status} />
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
