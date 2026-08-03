import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Plus } from "lucide-react";

import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/services/api";

export function JourneysListPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["dsl-journeys"],
    queryFn: api.listDslJourneys,
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h2 className="text-xl font-semibold">Journey definitions</h2>
          <p className="text-sm text-muted-foreground">DSL journeys stored in the engine.</p>
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
      ) : !data?.length ? (
        <EmptyState
          title="No journeys yet"
          description="Import or create a journey in the studio."
          action={
            <Button asChild>
              <Link to="/journeys/new/studio">Open studio</Link>
            </Button>
          }
        />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {data.map((j) => (
            <Card key={`${j.id}-${j.version}`}>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">{j.display_name || j.id}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <p className="text-xs text-muted-foreground font-mono">{j.id}</p>
                <p className="text-xs">v{j.version}</p>
                <Button variant="outline" size="sm" asChild>
                  <Link to={`/journeys/${j.id}/studio`}>Open studio</Link>
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
