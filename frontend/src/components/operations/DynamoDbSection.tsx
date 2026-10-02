import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, Table2 } from "lucide-react";
import {
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
  read_rcu: "border-l-sky-500",
  write_wcu: "border-l-amber-400",
  read_latency: "border-l-violet-500",
  write_latency: "border-l-green-500",
};

function formatKpi(kpi: DataStoreKpi): string {
  if (kpi.value == null) return "—";
  if (kpi.unit === "ms") return `${Number(kpi.value).toFixed(1)} ms`;
  if (kpi.unit === "RCU" || kpi.unit === "WCU") return `${Number(kpi.value).toFixed(2)} ${kpi.unit}`;
  return String(kpi.value);
}

function formatTick(iso: string, grain?: string): string {
  const d = new Date(iso);
  if (grain === "hour") {
    return d.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  }
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function DynamoDbSection() {
  const [window, setWindow] = useState<DataStoreWindow>("1h");
  const qc = useQueryClient();
  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["dynamodb-monitoring", window],
    queryFn: () => api.getDynamoOverview(window),
    refetchInterval: 60_000,
  });
  const points = (data?.points ?? []).map((p, idx) => ({
    ...p,
    idx,
    time: p.timestamp ? formatTick(p.timestamp, data?.grain) : "",
  }));
  const hasCapacity = points.some((p) => p.read_rcu != null || p.write_wcu != null);
  const hasLatency = points.some((p) => p.read_latency_ms != null || p.write_latency_ms != null);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Table2 className="h-5 w-5" />
            DynamoDB
          </CardTitle>
          <CardDescription>
            Journey, execution, prompt, and SLA snapshot tables used by this ai-engine. Capacity and
            latency come from CloudWatch when published; otherwise a Limit=1 read probe is used.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <select
              className="h-8 rounded-md border bg-background px-2 text-xs"
              value={window}
              onChange={(e) => setWindow(e.target.value as DataStoreWindow)}
              aria-label="DynamoDB window"
            >
              <option value="1h">Last 1h</option>
              <option value="24h">Last 24h</option>
              <option value="7d">Last 7 days</option>
            </select>
            <Button
              size="sm"
              onClick={() => qc.invalidateQueries({ queryKey: ["dynamodb-monitoring", window] })}
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
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 text-sm">
            <div className="border rounded-lg p-3">
              <div className="text-muted-foreground">Region</div>
              <div className="font-medium">{data?.region || "—"}</div>
            </div>
            <div className="border rounded-lg p-3">
              <div className="text-muted-foreground">Tables</div>
              <div className="font-medium">
                {data?.tables_active ?? 0} / {data?.table_total ?? 0} active
              </div>
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
          <CardTitle className="text-sm">Read / write capacity</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="h-[240px] flex items-center justify-center text-sm text-muted-foreground">Loading…</div>
          ) : !hasCapacity ? (
            <div className="h-[240px] flex items-center justify-center text-sm text-muted-foreground">
              No consumed capacity yet. CloudWatch RCU/WCU appears after table reads and writes.
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
                <YAxis tick={{ fontSize: 10 }} width={48} />
                <Tooltip
                  content={({ payload }) => {
                    if (!payload?.length) return null;
                    const time = (payload[0].payload as { time?: string })?.time;
                    return (
                      <div className="bg-background border rounded p-2 text-xs shadow space-y-1">
                        <div className="font-medium">{time}</div>
                        {payload.map((item) => (
                          <div key={String(item.dataKey)} style={{ color: String(item.color) }}>
                            {item.name}: {item.value != null ? Number(item.value).toFixed(2) : "—"}
                          </div>
                        ))}
                      </div>
                    );
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Line type="monotone" dataKey="read_rcu" name="Read RCU" stroke="#38bdf8" strokeWidth={2} dot={false} connectNulls />
                <Line type="monotone" dataKey="write_wcu" name="Write WCU" stroke="#eab308" strokeWidth={2} dot={false} connectNulls />
              </ComposedChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Read / write latency</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="h-[240px] flex items-center justify-center text-sm text-muted-foreground">Loading…</div>
          ) : !hasLatency ? (
            <div className="h-[240px] flex items-center justify-center text-sm text-muted-foreground">
              No latency samples yet. A read probe runs on refresh; write latency needs CloudWatch PutItem metrics.
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
                <YAxis tick={{ fontSize: 10 }} width={44} tickFormatter={(v) => `${v}`} />
                <Tooltip
                  content={({ payload }) => {
                    if (!payload?.length) return null;
                    const time = (payload[0].payload as { time?: string })?.time;
                    return (
                      <div className="bg-background border rounded p-2 text-xs shadow space-y-1">
                        <div className="font-medium">{time}</div>
                        {payload.map((item) => (
                          <div key={String(item.dataKey)} style={{ color: String(item.color) }}>
                            {item.name}: {item.value != null ? `${Number(item.value).toFixed(1)} ms` : "—"}
                          </div>
                        ))}
                      </div>
                    );
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Line type="monotone" dataKey="read_latency_ms" name="Read" stroke="#8b5cf6" strokeWidth={2} dot={false} connectNulls />
                <Line type="monotone" dataKey="write_latency_ms" name="Write" stroke="#22c55e" strokeWidth={2} dot={false} connectNulls />
              </ComposedChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Engine tables</CardTitle>
          <CardDescription>DescribeTable status plus latest consumed capacity when CloudWatch has it.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-sm border rounded-lg divide-y">
            {(data?.tables ?? []).map((row) => (
              <div key={row.id} className="px-3 py-2 space-y-1">
                <div className="flex justify-between gap-3">
                  <span className="font-medium">{row.label}</span>
                  <span className="text-muted-foreground">{row.status || "—"}</span>
                </div>
                <div className="font-mono text-xs break-all text-muted-foreground">{row.name || "not configured"}</div>
                <div className="text-xs text-muted-foreground">
                  {row.item_count != null ? `${row.item_count} items` : "item count n/a"}
                  {row.size_human ? ` · ${row.size_human}` : ""}
                  {row.gsi_count != null ? ` · ${row.gsi_count} GSI` : ""}
                  {row.billing_mode ? ` · ${row.billing_mode}` : ""}
                </div>
                <div className="text-xs text-muted-foreground">
                  read {row.read_rcu != null ? `${Number(row.read_rcu).toFixed(2)} RCU` : "n/a"}
                  {" · "}
                  write {row.write_wcu != null ? `${Number(row.write_wcu).toFixed(2)} WCU` : "n/a"}
                  {row.read_latency_ms != null ? ` · read ${Number(row.read_latency_ms).toFixed(1)} ms` : ""}
                  {row.write_latency_ms != null ? ` · write ${Number(row.write_latency_ms).toFixed(1)} ms` : ""}
                </div>
              </div>
            ))}
            {isLoading ? <div className="px-3 py-4 text-muted-foreground">Loading tables…</div> : null}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
