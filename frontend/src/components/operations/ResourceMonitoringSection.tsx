import { useState } from "react";
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
import type { ResourceKpi, ResourceWindow } from "@/types/resourceMonitoring";

const KPI_TINT: Record<string, string> = {
  cpu: "border-l-violet-500",
  memory: "border-l-blue-500",
  storage: "border-l-amber-400",
  network: "border-l-sky-500",
  jobs: "border-l-green-500",
};

function formatKpi(kpi: ResourceKpi): string {
  if (kpi.value == null) return "—";
  if (kpi.unit === "%") return `${Number(kpi.value).toFixed(1)}%`;
  if (kpi.unit === "Mbps") return `${Number(kpi.value).toFixed(2)} Mbps`;
  return String(Math.round(Number(kpi.value)));
}

function formatTick(iso: string, grain?: string): string {
  const d = new Date(iso);
  if (grain === "hour") {
    return d.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  }
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}


export function ResourceMonitoringSection() {
  const [window, setWindow] = useState<ResourceWindow>("1h");
  const qc = useQueryClient();
  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["resource-monitoring", window],
    queryFn: () => api.getResourceUsage(window),
    refetchInterval: 30_000,
  });

  const points = (data?.points ?? []).map((p, idx) => ({
    ...p,
    idx,
    jobs_running: Number(p.jobs_running ?? 0),
    time: formatTick(p.timestamp, data?.grain),
  }));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold">Resource Monitoring</h3>
          <p className="text-sm text-muted-foreground">
            Local K3s node usage{data?.node ? ` · ${data.node}` : ""} with running job count.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            className="h-8 rounded-md border bg-background px-2 text-xs"
            value={window}
            onChange={(e) => setWindow(e.target.value as ResourceWindow)}
            aria-label="Resource window"
          >
            <option value="1h">Last 1h</option>
            <option value="24h">Last 24h</option>
            <option value="7d">Last 7 days</option>
          </select>
          <Button
            variant="outline"
            size="sm"
            className="h-8"
            onClick={() => qc.invalidateQueries({ queryKey: ["resource-monitoring", window] })}
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
        {(isLoading ? Array.from({ length: 5 }).map((_, i) => ({ id: String(i) }) as ResourceKpi) : data?.kpis ?? []).map(
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
          <CardTitle className="text-sm">CPU, memory, and storage</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="h-[240px] flex items-center justify-center text-sm text-muted-foreground">Loading…</div>
          ) : data?.error ? (
            <div className="h-[240px] flex items-center justify-center text-sm text-red-500">{data.error}</div>
          ) : points.length === 0 ? (
            <div className="h-[240px] flex items-center justify-center text-sm text-muted-foreground">
              No resource samples yet.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <ComposedChart data={points}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
                <XAxis
                  dataKey="idx"
                  type="number"
                  domain={["dataMin", "dataMax"]}
                  tickFormatter={(idx) => points[Number(idx)]?.time ?? ""}
                  tick={{ fontSize: 10 }}
                  interval="preserveStartEnd"
                  minTickGap={28}
                />
                <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} tickFormatter={(v) => `${v}%`} width={40} />
                <Tooltip
                  content={({ payload }) => {
                    if (!payload?.length) return null;
                    const time = (payload[0].payload as { time?: string })?.time;
                    return (
                      <div className="bg-background border rounded p-2 text-xs shadow space-y-1">
                        <div className="font-medium">{time}</div>
                        {payload.map((item) => (
                          <div key={String(item.dataKey)} style={{ color: String(item.color) }}>
                            {item.name}: {item.value != null ? `${Number(item.value).toFixed(1)}%` : "—"}
                          </div>
                        ))}
                      </div>
                    );
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Line type="monotone" dataKey="cpu_pct" name="CPU" stroke="#8b5cf6" strokeWidth={2} dot={false} connectNulls />
                <Line type="monotone" dataKey="memory_pct" name="Memory" stroke="#3b82f6" strokeWidth={2} dot={false} connectNulls />
                <Line type="monotone" dataKey="storage_pct" name="Storage" stroke="#eab308" strokeWidth={2} dot={false} connectNulls />
              </ComposedChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Network and running jobs</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading || points.length === 0 ? (
            <div className="h-[240px] flex items-center justify-center text-sm text-muted-foreground">
              {isLoading ? "Loading…" : "No network samples yet. Rates appear after a second scrape."}
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <ComposedChart data={points}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
                <XAxis
                  dataKey="idx"
                  type="number"
                  domain={["dataMin", "dataMax"]}
                  tickFormatter={(idx) => points[Number(idx)]?.time ?? ""}
                  tick={{ fontSize: 10 }}
                  interval="preserveStartEnd"
                  minTickGap={28}
                />
                <YAxis yAxisId="net" tick={{ fontSize: 10 }} width={44} tickFormatter={(v) => `${v}`} />
                <YAxis yAxisId="jobs" orientation="right" allowDecimals={false} tick={{ fontSize: 10 }} width={36} />
                <Tooltip
                  content={({ payload }) => {
                    if (!payload?.length) return null;
                    const time = (payload[0].payload as { time?: string })?.time;
                    return (
                      <div className="bg-background border rounded p-2 text-xs shadow space-y-1">
                        <div className="font-medium">{time}</div>
                        {payload.map((item) => (
                          <div key={String(item.dataKey)} style={{ color: String(item.color) }}>
                            {item.name}:{" "}
                            {item.dataKey === "jobs_running"
                              ? Number(item.value ?? 0)
                              : item.value != null
                                ? Number(item.value).toFixed(3)
                                : "—"}
                          </div>
                        ))}
                      </div>
                    );
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar yAxisId="jobs" dataKey="jobs_running" name="Jobs running" fill="#22c55e80" maxBarSize={14} minPointSize={0} />
                <Line
                  yAxisId="net"
                  type="monotone"
                  dataKey="network_rx_mbps"
                  name="Rx Mbps"
                  stroke="#38bdf8"
                  strokeWidth={2}
                  dot={false}
                  connectNulls
                />
                <Line
                  yAxisId="net"
                  type="monotone"
                  dataKey="network_tx_mbps"
                  name="Tx Mbps"
                  stroke="#f97316"
                  strokeWidth={2}
                  dot={false}
                  connectNulls
                />
              </ComposedChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
