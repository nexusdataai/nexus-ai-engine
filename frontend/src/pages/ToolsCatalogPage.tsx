import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { EmptyState } from "@/components/EmptyState";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/services/api";

export function ToolsCatalogPage() {
  const [domain, setDomain] = useState("");
  const { data, isLoading, error } = useQuery({
    queryKey: ["tools", domain],
    queryFn: () => api.listTools(domain || undefined),
  });

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold">Tools catalog</h2>
        <p className="text-sm text-muted-foreground">Read-only view of published tool packages.</p>
      </div>

      <input
        type="search"
        placeholder="Filter by domain…"
        className="max-w-xs w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
        value={domain}
        onChange={(e) => setDomain(e.target.value)}
        aria-label="Filter by domain"
      />

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading tools…</p>
      ) : error ? (
        <EmptyState title="Could not load tools" description={String(error)} />
      ) : !data?.tools.length ? (
        <EmptyState title="No tools" description="Publish tool packages via POST /api/v1/tool-packages." />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" data-testid="tools-catalog">
          {data.tools.map((t) => (
            <Card key={`${t.id}-${t.version}`}>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">{t.display_name || t.id}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-1 text-sm">
                <p className="font-mono text-xs text-muted-foreground">{t.id}</p>
                <p className="text-xs">v{t.version} · {t.domain}</p>
                {t.description ? <p className="text-muted-foreground">{t.description}</p> : null}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
