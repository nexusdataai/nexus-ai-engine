import { useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/services/api";
import type { AppTrendKpi, AppTrendsTab, AppTrendsWindow } from "@/types/appTrends";
import { useState } from "react";

const KPI_TINT: Record<string, string> = {
  active: "border-l-blue-500",
  submitted: "border-l-violet-500",
  succeeded: "border-l-green-500",
  failed: "border-l-red-500",
  success_rate: "border-l-amber-400",
  p95: "border-l-sky-500",
  waiting: "border-l-violet-500",
  running: "border-l-blue-500",
  pending: "border-l-slate-400",
  capacity: "border-l-sky-500",
  slots: "border-l-indigo-400",
  lag_pct: "border-l-amber-400",
  total: "border-l-blue-500",
  enabled: "border-l-green-500",
  due_soon: "border-l-violet-500",
  last_failed: "border-l-red-500",
  fired: "border-l-sky-500",
};

function formatKpi(kpi: AppTrendKpi): string {
  if (kpi.value == null) return "—";
  if (kpi.unit === "%") return `${Number(kpi.value).toFixed(1)}%`;
  if (kpi.unit === "ms") return `${Math.round(Number(kpi.value))}ms`;
  return String(Math.round(Number(kpi.value)));
}

function formatTick(iso: string, grain?: string): string {
  const d = new Date(iso);
  if (grain === "day") {
    return d.toLocaleDateString([], { month: "short", day: "numeric" });
  }
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function AppTrendsSection({ tab }: { tab: AppTrendsTab }) {
  const [window, setWindow] = useState<AppTrendsWindow>("24h");
  const qc = useQueryClient();
  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["app-trends", tab, window],
    queryFn: () => api.getAppTrends(tab, window),
    refetchInterval: 60_000,
  });

  const points = (data?.points ?? []).map((p) => ({
    ...p,
    time: formatTick(p.timestamp, data?.grain),
    rate: p.rate ?? null,
  }));
  const mixTotal = (data?.mix ?? []).reduce((n, m) => n + (m.value || 0), 0);
  const countSeries = (data?.series ?? []).filter((s) => s.axis === "count" && s.id !== "rate");
  const rateSeries = (data?.series ?? []).find((s) => s.axis === "percent");

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold">
            {tab === "executions" ? "Executions" : tab === "queue" ? "Queue" : "Schedules"} trends
          </h3>
          <p className="text-sm text-muted-foreground">
            {data?.chart_title ?? "Volume over time with a quality/rate overlay."}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            className="h-8 rounded-md border bg-background px-2 text-xs"
            value={window}
            onChange={(e) => setWindow(e.target.value as AppTrendsWindow)}
            aria-label="Trend window"
          >
            <option value="24h">Last 24h</option>
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
          </select>
          <Button
            variant="outline"
            size="sm"
            className="h-8"
            onClick={() => qc.invalidateQueries({ queryKey: ["app-trends", tab, window] })}
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {(isLoading ? Array.from({ length: 6 }).map((_, i) => ({ id: String(i) }) as AppTrendKpi) : data?.kpis ?? []).map(
          (kpi) => (
            <Card key={kpi.id} className={`border-l-4 ${KPI_TINT[kpi.id] ?? "border-l-primary"}`}>
              <CardContent className="p-4">
                {isLoading ? (
                  <div className="h-12 animate-pulse rounded bg-muted" />
                ) : (
                  <>
                    <div className="text-[11px] uppercase tracking-wide text-muted-foreground">{kpi.label}</div>
                    <div className="mt-1 text-2xl font-bold">{formatKpi(kpi)}</div>
                  </>
                )}
              </CardContent>
            </Card>
          ),
        )}
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">{data?.chart_title ?? "Trend"}</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="h-[280px] flex items-center justify-center text-sm text-muted-foreground">Loading…</div>
          ) : data?.error ? (
            <div className="h-[280px] flex items-center justify-center text-sm text-red-500">{data.error}</div>
          ) : points.length === 0 ? (
            <div className="h-[280px] flex items-center justify-center text-sm text-muted-foreground">
              No trend data yet for this window.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <ComposedChart data={points}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
                <XAxis dataKey="time" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                <YAxis yAxisId="count" tick={{ fontSize: 10 }} width={36} />
                <YAxis
                  yAxisId="percent"
                  orientation="right"
                  domain={[0, 100]}
                  tick={{ fontSize: 10 }}
                  tickFormatter={(v) => `${v}%`}
                  width={40}
                />
                <Tooltip
                  content={({ payload, label }) => {
                    if (!payload?.length) return null;
                    return (
                      <div className="bg-background border rounded p-2 text-xs shadow space-y-1">
                        <div className="font-medium">{label}</div>
                        {payload.map((item) => (
                          <div key={String(item.dataKey)} style={{ color: String(item.color) }}>
                            {item.name}: {item.value}
                            {item.dataKey === "rate" ? "%" : ""}
                          </div>
                        ))}
                      </div>
                    );
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                {countSeries.map((s) => (
                  <Bar
                    key={s.id}
                    yAxisId="count"
                    dataKey={s.id}
                    name={s.label}
                    stackId="volume"
                    fill={s.color}
                    maxBarSize={28}
                  />
                ))}
                {rateSeries ? (
                  <Line
                    yAxisId="percent"
                    type="monotone"
                    dataKey="rate"
                    name={rateSeries.label}
                    stroke={rateSeries.color}
                    strokeWidth={2}
                    dot={false}
                    connectNulls
                  />
                ) : null}
              </ComposedChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      {data?.mix && mixTotal > 0 ? (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Mix</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex h-3 w-full overflow-hidden rounded-full">
              {data.mix.map((m) => (
                <div
                  key={m.id}
                  style={{
                    width: `${Math.max(0, (m.value / mixTotal) * 100)}%`,
                    backgroundColor: m.color,
                  }}
                  title={`${m.label}: ${m.value}`}
                />
              ))}
            </div>
            <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
              {data.mix.map((m) => (
                <span key={m.id} className="inline-flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full" style={{ backgroundColor: m.color }} />
                  {m.label} {((m.value / mixTotal) * 100).toFixed(0)}%
                </span>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
