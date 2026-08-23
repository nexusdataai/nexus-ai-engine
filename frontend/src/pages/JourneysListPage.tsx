import { useQueries } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Plus } from "lucide-react";

import { EmptyState } from "@/components/EmptyState";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/services/api";
import type { DslJourneySummary, SimpleJourneySummary } from "@/types/api";

function JourneyGrid({ children }: { children: React.ReactNode }) {
  return <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{children}</div>;
}

function SimpleJourneyCard({ journey }: { journey: SimpleJourneySummary }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-base">{journey.name}</CardTitle>
          <StatusBadge status={journey.status} />
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        {journey.description ? (
          <p className="text-sm text-muted-foreground line-clamp-2">{journey.description}</p>
        ) : null}
        <p className="text-xs text-muted-foreground font-mono">{journey.journeyId}</p>
        {journey.odaComponentType ? (
          <p className="text-xs text-muted-foreground capitalize">{journey.odaComponentType.replace(/-/g, " ")}</p>
        ) : null}
        <Button variant="outline" size="sm" asChild>
          <Link to="/executions">View executions</Link>
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
          <Link to={`/journeys/${journey.id}/studio`}>Open studio</Link>
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
          <h2 className="text-xl font-semibold">Journey definitions</h2>
          <p className="text-sm text-muted-foreground">
            Stage-based and DSL journeys stored in the engine.
          </p>
        </div>
        <Button asChild>
          <Link to="/journeys/new/studio">
            <Plus className="h-4 w-4" />
            New journey
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
          description="Import or create a journey in the studio, or seed sample journeys for local dev."
          action={
            <Button asChild>
              <Link to="/journeys/new/studio">Open studio</Link>
            </Button>
          }
        />
      ) : (
        <>
          {simpleJourneys.length > 0 ? (
            <section className="space-y-3" data-testid="simple-journeys">
              <div>
                <h3 className="text-sm font-medium">Stage-based journeys</h3>
                <p className="text-xs text-muted-foreground">
                  Legacy journeys with configured stages and batch schedules.
                </p>
              </div>
              <JourneyGrid>
                {simpleJourneys.map((j) => (
                  <SimpleJourneyCard key={j.journeyId} journey={j} />
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
