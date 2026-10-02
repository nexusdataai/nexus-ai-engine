import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, Warehouse } from "lucide-react";
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
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/services/api";
import type { DataStoreKpi, DataStoreWindow } from "@/types/dataStores";

const KPI_TINT: Record<string, string> = {
  read_queries: "border-l-sky-500",
  write_queries: "border-l-amber-400",
  bytes_scanned: "border-l-violet-500",
  avg_engine_ms: "border-l-green-500",
};

function formatBytes(value?: number | null): string {
  if (value == null) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let n = Number(value);
  let idx = 0;
  while (n >= 1024 && idx < units.length - 1) {
    n /= 1024;
    idx += 1;
  }
  return `${n.toFixed(2)} ${units[idx]}`;
}

function formatKpi(kpi: DataStoreKpi): string {
  if (kpi.value == null) return "—";
  if (kpi.unit === "ms") return `${Math.round(Number(kpi.value))} ms`;
  if (kpi.unit === "bytes") return formatBytes(kpi.value);
  return String(Math.round(Number(kpi.value)));
}

function formatTick(iso: string, grain?: string): string {
  const d = new Date(iso);
  if (grain === "hour") {
    return d.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  }
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function AthenaSection() {
  const [window, setWindow] = useState<DataStoreWindow>("7d");
  const qc = useQueryClient();
  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["athena-monitoring", window],
    queryFn: () => api.getAthenaOverview(window),
    refetchInterval: 60_000,
  });
  const table = data?.table;
  const points = (data?.points ?? []).map((p, idx) => ({
    ...p,
    idx,
    time: p.timestamp ? formatTick(p.timestamp, data?.grain) : "",
  }));
  const hasTrend = points.some(
    (p) => p.read_queries != null || p.write_queries != null || p.bytes_scanned != null || p.avg_engine_ms != null,
  );

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Warehouse className="h-5 w-5" />
            Athena Database
          </CardTitle>
          <CardDescription>
            Glue catalog and Athena workgroup used for archived job search. Read/write comes from
            SELECT vs INSERT/CTAS/UNLOAD executions. Page load does not start a new query.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <select
              className="h-8 rounded-md border bg-background px-2 text-xs"
              value={window}
              onChange={(e) => setWindow(e.target.value as DataStoreWindow)}
              aria-label="Athena window"
            >
              <option value="1h">Last 1h</option>
              <option value="24h">Last 24h</option>
              <option value="7d">Last 7 days</option>
            </select>
            <Button
              size="sm"
              onClick={() => qc.invalidateQueries({ queryKey: ["athena-monitoring", window] })}
              disabled={isLoading}
            >
              <RefreshCw className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`} />
              Refresh Status
            </Button>
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                data?.connected ? "bg-emerald-600/20 text-emerald-400" : "bg-red-600/20 text-red-400"
              }`}
            >
              {isLoading ? "checking" : data?.connected ? "connected" : "disconnected"}
            </span>
            {data?.ping_ms != null && <span className="text-sm text-muted-foreground">{data.ping_ms} ms</span>}
            {data?.points_scope === "recent" ? (
              <span className="text-xs text-muted-foreground">Showing last workgroup executions (none in this window)</span>
            ) : null}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 text-sm">
            <div className="border rounded-lg p-3">
              <div className="text-muted-foreground">Region</div>
              <div className="font-medium">{data?.region || "—"}</div>
            </div>
            <div className="border rounded-lg p-3">
              <div className="text-muted-foreground">Glue / Athena</div>
              <div className="font-medium">
                {data?.glue_reachable ? "up" : "down"} / {data?.athena_reachable ? "up" : "down"}
              </div>
            </div>
            <div className="border rounded-lg p-3">
              <div className="text-muted-foreground">Database</div>
              <div className="font-medium">{data?.database || "—"}</div>
            </div>
            <div className="border rounded-lg p-3">
              <div className="text-muted-foreground">Workgroup</div>
              <div className="font-medium">{data?.workgroup || "—"}</div>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {(isLoading ? Array.from({ length: 4 }).map((_, i) => ({ id: String(i) }) as DataStoreKpi) : data?.kpis ?? []).map(
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
          <CardTitle className="text-sm">Read / write query trend</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="h-[240px] flex items-center justify-center text-sm text-muted-foreground">Loading…</div>
          ) : !hasTrend ? (
            <div className="h-[240px] flex items-center justify-center text-sm text-muted-foreground">
              No Athena query executions to chart yet.
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
                <YAxis yAxisId="count" allowDecimals={false} tick={{ fontSize: 10 }} width={36} />
                <YAxis yAxisId="bytes" orientation="right" tick={{ fontSize: 10 }} width={56} tickFormatter={(v) => formatBytes(v)} />
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
                            {item.dataKey === "bytes_scanned"
                              ? formatBytes(item.value as number)
                              : item.value != null
                                ? Number(item.value)
                                : "—"}
                          </div>
                        ))}
                      </div>
                    );
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar yAxisId="count" dataKey="read_queries" name="Read queries" fill="#38bdf880" maxBarSize={14} />
                <Bar yAxisId="count" dataKey="write_queries" name="Write queries" fill="#eab30880" maxBarSize={14} />
                <Line
                  yAxisId="bytes"
                  type="monotone"
                  dataKey="bytes_scanned"
                  name="Data scanned"
                  stroke="#8b5cf6"
                  strokeWidth={2}
                  dot={false}
                  connectNulls
                />
              </ComposedChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Engine time</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading || !hasTrend ? (
            <div className="h-[240px] flex items-center justify-center text-sm text-muted-foreground">
              {isLoading ? "Loading…" : "No engine-time samples yet."}
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
                <YAxis tick={{ fontSize: 10 }} width={44} tickFormatter={(v) => `${v} ms`} />
                <Tooltip
                  content={({ payload }) => {
                    if (!payload?.length) return null;
                    const time = (payload[0].payload as { time?: string })?.time;
                    return (
                      <div className="bg-background border rounded p-2 text-xs shadow space-y-1">
                        <div className="font-medium">{time}</div>
                        {payload.map((item) => (
                          <div key={String(item.dataKey)} style={{ color: String(item.color) }}>
                            {item.name}: {item.value != null ? `${Number(item.value).toFixed(0)} ms` : "—"}
                          </div>
                        ))}
                      </div>
                    );
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Line type="monotone" dataKey="avg_engine_ms" name="Avg engine" stroke="#22c55e" strokeWidth={2} dot={false} connectNulls />
              </ComposedChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Archived jobs table</CardTitle>
          <CardDescription>
            Glue table {table?.name || "archived_jobs"} used when Dynamo job history is archived.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="border rounded-lg p-3">
              <div className="text-muted-foreground">Exists</div>
              <div className="font-medium">{table?.exists ? "yes" : "no"}</div>
            </div>
            <div className="border rounded-lg p-3">
              <div className="text-muted-foreground">Partitions</div>
              <div className="font-medium">
                {table?.partition_count ?? "—"}
                {table?.partitions_truncated ? "+" : ""}
              </div>
            </div>
            <div className="border rounded-lg p-3">
              <div className="text-muted-foreground">Record count</div>
              <div className="font-medium">{table?.record_count ?? "—"}</div>
            </div>
            <div className="border rounded-lg p-3">
              <div className="text-muted-foreground">Archive bucket</div>
              <div className="font-medium break-all">{data?.archive_bucket || "—"}</div>
            </div>
          </div>
          {table?.location ? (
            <div className="text-xs font-mono break-all text-muted-foreground">{table.location}</div>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Recent Athena queries</CardTitle>
          <CardDescription>Last executions in this workgroup. Page load does not start a new query.</CardDescription>
        </CardHeader>
        <CardContent>
          {(data?.recent_queries || []).length === 0 ? (
            <p className="text-sm text-muted-foreground">{isLoading ? "Loading…" : "No recent query executions."}</p>
          ) : (
            <div className="text-sm border rounded-lg divide-y">
              {(data?.recent_queries || []).map((q) => (
                <div key={q.id} className="flex justify-between gap-3 px-3 py-2">
                  <span className="font-mono break-all">{q.id}</span>
                  <span className="text-muted-foreground shrink-0">
                    {q.kind || "—"}
                    {q.state ? ` · ${q.state}` : ""}
                    {q.engine_ms != null ? ` · ${q.engine_ms} ms` : ""}
                    {q.bytes_scanned_human ? ` · ${q.bytes_scanned_human}` : ""}
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
