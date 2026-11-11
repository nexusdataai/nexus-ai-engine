import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { CodeBlock, EmptyState, InlineError, PageHeader, SearchInput, SkeletonRows, TableShell, Toolbar } from "@/components/ds/kit";
import { api } from "@/services/api";

export function ToolsCatalogPage() {
  const [domain, setDomain] = useState("");
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["tools", domain],
    queryFn: () => api.listTools(domain || undefined),
  });

  const tools = data?.tools ?? [];

  return (
    <div className="space-y-5">
      <PageHeader
        title="Tools catalog"
        description={
          <>
            Read-only view of published tool packages.
            {!isLoading && !error && tools.length > 0 ? (
              <span className="text-foreground"> <span className="num font-medium">{tools.length}</span> published.</span>
            ) : null}
          </>
        }
      />

      <Toolbar>
        <SearchInput value={domain} onChange={setDomain} placeholder="Filter by domain…" type="search" aria-label="Filter by domain" />
      </Toolbar>

      {isLoading ? (
        <TableShell>
          <SkeletonRows rows={4} />
        </TableShell>
      ) : error ? (
        <InlineError onRetry={() => refetch()}>Could not load tools. {String(error)}</InlineError>
      ) : !tools.length ? (
        <EmptyState
          icon="wrench"
          title="No tools"
          description={
            domain
              ? `No tool packages are published in the "${domain}" domain.`
              : "Journeys call tools to do their work. Publish a tool package and it appears here for every journey to use."
          }
          action={
            <div className="w-full max-w-md text-left">
              <CodeBlock>POST /api/v1/tool-packages</CodeBlock>
            </div>
          }
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3" data-testid="tools-catalog">
          {tools.map((t) => (
            <article
              key={`${t.id}-${t.version}`}
              className="flex min-w-0 flex-col rounded-xl border border-border bg-card p-5 shadow-xs transition-[border-color,box-shadow,transform] duration-200 ease-brand hover:-translate-y-0.5 hover:border-brand/40 hover:shadow-md"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="truncate text-md font-medium text-foreground">{t.display_name || t.id}</h3>
                  <p className="mono-id truncate">{t.id}</p>
                </div>
                <span className="num shrink-0 rounded border border-border-strong px-1.5 py-px text-xs text-muted-foreground">v{t.version}</span>
              </div>
              {t.description ? <p className="mt-3 line-clamp-3 text-sm text-muted-foreground">{t.description}</p> : null}
              <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-border pt-3 text-xs text-muted-foreground">
                <span>
                  Domain <span className="font-medium text-foreground">{t.domain}</span>
                </span>
                {t.capabilities?.length ? (
                  <span>
                    <span className="num font-medium text-foreground">{t.capabilities.length}</span> capabilities
                  </span>
                ) : null}
              </div>
              {t.capabilities?.length ? (
                <ul className="mt-2 flex flex-wrap gap-1.5">
                  {t.capabilities.map((c) => (
                    <li key={c.name} title={c.description} className="rounded-md border border-border bg-surface-2 px-2 py-0.5 text-xs text-muted-foreground">
                      {c.display_name || c.name}
                    </li>
                  ))}
                </ul>
              ) : null}
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
