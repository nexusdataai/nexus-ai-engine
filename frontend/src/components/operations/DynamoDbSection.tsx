import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  CHART_MARGIN,
  ChartLegend,
  ChartTooltip,
  axisProps,
  cursorLine,
  gridProps,
  lineProps,
  seriesColor,
} from "@/components/ds/charts";
import { EmptyState, MetricStrip, Panel, Segmented, SkeletonRows, StatusPill, type ChipOption, type Metric } from "@/components/ds/kit";
import { api } from "@/services/api";
import type { DataStoreKpi, DataStoreWindow } from "@/types/dataStores";

import { ChartBody, ConnectionPill, MetricStripSkeleton, RefreshButton, SectionHeader, stripColumns } from "./parts";

const WINDOWS: ChipOption<DataStoreWindow>[] = [
  { value: "1h", label: "Last 1h" },
  { value: "24h", label: "Last 24h" },
  { value: "7d", label: "Last 7 days" },
];

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

const NA = <span className="text-subtle-foreground">n/a</span>;

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
  const timeOf = (idx: unknown) => points[Number(idx)]?.time ?? "";
  const tables = data?.tables ?? [];

  const summary: Metric[] = [
    { label: "Region", value: data?.region || "—" },
    { label: "Tables", value: `${data?.tables_active ?? 0} / ${data?.table_total ?? 0} active` },
    ...(data?.kpis ?? []).map((kpi) => ({ label: kpi.label, value: formatKpi(kpi) })),
  ];

  return (
    <div className="space-y-6">
      <SectionHeader
        title="DynamoDB"
        description="Journey, execution, prompt, and SLA snapshot tables used by this ai-engine. Capacity and latency come from CloudWatch when published; otherwise a Limit=1 read probe is used."
        meta={
          <>
            <ConnectionPill loading={isLoading} connected={data?.connected} />
            {data?.ping_ms != null && <span className="num text-sm text-muted-foreground">{data.ping_ms} ms</span>}
          </>
        }
        actions={
          <>
            <Segmented options={WINDOWS} value={window} onChange={setWindow} label="DynamoDB window" />
            <RefreshButton
              spinning={isFetching}
              disabled={isLoading}
              onClick={() => qc.invalidateQueries({ queryKey: ["dynamodb-monitoring", window] })}
            >
              Refresh Status
            </RefreshButton>
          </>
        }
      />

      {isLoading ? <MetricStripSkeleton count={6} /> : <MetricStrip items={summary} columns={stripColumns(summary.length)} />}

      <div className="grid gap-6 xl:grid-cols-2">
        <Panel title="Read / write capacity">
          <ChartBody
            loading={isLoading}
            empty={!hasCapacity && "No consumed capacity yet. CloudWatch RCU/WCU appears after table reads and writes."}
          >
            <ResponsiveContainer width="100%" height={240}>
              <ComposedChart data={points} margin={CHART_MARGIN}>
                <CartesianGrid {...gridProps} />
                <XAxis
                  dataKey="idx"
                  type="number"
                  domain={["dataMin", "dataMax"]}
                  tickFormatter={timeOf}
                  {...axisProps}
                  interval="preserveStartEnd"
                  minTickGap={28}
                />
                <YAxis {...axisProps} width={48} />
                <Tooltip
                  cursor={cursorLine}
                  content={
                    <ChartTooltip
                      labelFormatter={timeOf}
                      valueFormatter={(value) => (value != null ? Number(value).toFixed(2) : "—")}
                    />
                  }
                />
                <Line dataKey="read_rcu" name="Read RCU" stroke={seriesColor(0)} {...lineProps} connectNulls />
                <Line dataKey="write_wcu" name="Write WCU" stroke={seriesColor(1)} {...lineProps} connectNulls />
              </ComposedChart>
            </ResponsiveContainer>
            <ChartLegend
              className="mt-3"
              items={[
                { label: "Read RCU", color: seriesColor(0) },
                { label: "Write WCU", color: seriesColor(1) },
              ]}
            />
          </ChartBody>
        </Panel>

        <Panel title="Read / write latency">
          <ChartBody
            loading={isLoading}
            empty={!hasLatency && "No latency samples yet. A read probe runs on refresh; write latency needs CloudWatch PutItem metrics."}
          >
            <ResponsiveContainer width="100%" height={240}>
              <ComposedChart data={points} margin={CHART_MARGIN}>
                <CartesianGrid {...gridProps} />
                <XAxis
                  dataKey="idx"
                  type="number"
                  domain={["dataMin", "dataMax"]}
                  tickFormatter={timeOf}
                  {...axisProps}
                  interval="preserveStartEnd"
                  minTickGap={28}
                />
                <YAxis {...axisProps} width={44} tickFormatter={(v) => `${v}`} />
                <Tooltip
                  cursor={cursorLine}
                  content={
                    <ChartTooltip
                      labelFormatter={timeOf}
                      valueFormatter={(value) => (value != null ? `${Number(value).toFixed(1)} ms` : "—")}
                    />
                  }
                />
                <Line dataKey="read_latency_ms" name="Read" stroke={seriesColor(0)} {...lineProps} connectNulls />
                <Line dataKey="write_latency_ms" name="Write" stroke={seriesColor(1)} {...lineProps} connectNulls />
              </ComposedChart>
            </ResponsiveContainer>
            <ChartLegend
              className="mt-3"
              items={[
                { label: "Read", color: seriesColor(0) },
                { label: "Write", color: seriesColor(1) },
              ]}
            />
          </ChartBody>
        </Panel>
      </div>

      <Panel
        title="Engine tables"
        flush
        footer="DescribeTable status plus latest consumed capacity when CloudWatch has it."
      >
        {isLoading ? (
          <SkeletonRows rows={4} />
        ) : tables.length === 0 ? (
          <EmptyState bare icon="table" title="No engine tables" />
        ) : (
          <div className="scroll-thin overflow-x-auto">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Table</th>
                  <th>Status</th>
                  <th className="r">Items</th>
                  <th className="r">Size</th>
                  <th className="r">GSI</th>
                  <th>Billing</th>
                  <th className="r">Read RCU</th>
                  <th className="r">Write WCU</th>
                  <th className="r">Read ms</th>
                  <th className="r">Write ms</th>
                </tr>
              </thead>
              <tbody>
                {tables.map((row) => (
                  <tr key={row.id}>
                    <td className="min-w-[220px]">
                      <span className="block font-medium text-foreground">{row.label}</span>
                      <span className="block break-all font-mono text-xs text-muted-foreground">{row.name || "not configured"}</span>
                    </td>
                    <td>{row.status ? <StatusPill status={row.status} /> : "—"}</td>
                    <td className="r num">{row.item_count != null ? row.item_count : NA}</td>
                    <td className="r num whitespace-nowrap">{row.size_human || "—"}</td>
                    <td className="r num">{row.gsi_count != null ? row.gsi_count : "—"}</td>
                    <td className="whitespace-nowrap text-muted-foreground">{row.billing_mode || "—"}</td>
                    <td className="r num">{row.read_rcu != null ? Number(row.read_rcu).toFixed(2) : NA}</td>
                    <td className="r num">{row.write_wcu != null ? Number(row.write_wcu).toFixed(2) : NA}</td>
                    <td className="r num">{row.read_latency_ms != null ? Number(row.read_latency_ms).toFixed(1) : "—"}</td>
                    <td className="r num">{row.write_latency_ms != null ? Number(row.write_latency_ms).toFixed(1) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}
