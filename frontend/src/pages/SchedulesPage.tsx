import { useQuery } from "@tanstack/react-query";

import { EmptyState } from "@/components/EmptyState";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/services/api";

export function SchedulesPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["schedules"],
    queryFn: () => api.listSchedules(),
  });

  const rows = data?.data ?? [];

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold">Batch schedules</h2>
        <p className="text-sm text-muted-foreground">Periodic stage runs configured in the engine.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Schedules</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : error ? (
            <EmptyState title="Could not load schedules" description={String(error)} />
          ) : rows.length === 0 ? (
            <EmptyState title="No schedules" description="Create schedules via the API or embedded UI." />
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted-foreground border-b border-border">
                  <th className="py-2 pr-4">Journey</th>
                  <th className="py-2 pr-4">Stage</th>
                  <th className="py-2 pr-4">Interval</th>
                  <th className="py-2">Enabled</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((s) => (
                  <tr key={s.schedule_id} className="border-b border-border/50">
                    <td className="py-2 pr-4">{s.journey_id}</td>
                    <td className="py-2 pr-4">{s.stage_id}</td>
                    <td className="py-2 pr-4">{s.interval_minutes} min</td>
                    <td className="py-2">{s.enabled ? "Yes" : "No"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
