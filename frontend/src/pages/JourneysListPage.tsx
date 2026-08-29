import { useQueries } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Plus } from "lucide-react";

import { EmptyState } from "@/components/EmptyState";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { journeyListStats } from "@/lib/stageJourney";
import { api } from "@/services/api";
import type { DslJourneySummary, SimpleJourneySummary } from "@/types/api";

function JourneyGrid({ children }: { children: React.ReactNode }) {
  return <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{children}</div>;
}

function JourneyCard({ journey }: { journey: SimpleJourneySummary }) {
  const stats = journeyListStats(journey);

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-base">{journey.name}</CardTitle>
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
        <Button variant="outline" size="sm" asChild>
          <Link to={`/journeys/${journey.journeyId}`}>Open journey</Link>
        </Button>
      </CardContent>
    </Card>
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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h2 className="text-xl font-semibold">Journeys</h2>
          <p className="text-sm text-muted-foreground">
            Stage-based pipelines and YAML-defined DSL journeys.
          </p>
        </div>
        <Button asChild>
          <Link to="/journeys/new/studio">
            <Plus className="h-4 w-4" />
            New DSL journey
          </Link>
        </Button>
      </div>

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
              <JourneyGrid>
                {simpleJourneys.map((j) => (
                  <JourneyCard key={j.journeyId} journey={j} />
                ))}
              </JourneyGrid>
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
