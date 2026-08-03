import { useQuery } from "@tanstack/react-query";

import { api } from "@/services/api";

export function ScaffoldPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["version"],
    queryFn: () => api.version(),
  });

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center gap-4 p-8">
      <h1 className="text-3xl font-semibold tracking-tight">Journey Studio</h1>
      <p className="text-muted-foreground">
        Nexus AI Engine v0.3.0 frontend scaffold — Vite, React 18, TypeScript, Tailwind, TanStack Query.
      </p>
      <div className="rounded-lg border border-border bg-card p-4 text-sm">
        {isLoading && <span>Connecting to API…</span>}
        {error && <span className="text-destructive">API offline (start `make serve` on :8000)</span>}
        {data && (
          <span>
            API version: <strong>{data.version}</strong>
          </span>
        )}
      </div>
    </main>
  );
}
