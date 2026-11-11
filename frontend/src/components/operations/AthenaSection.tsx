import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bar,
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
  barProps,
  cursorBand,
  cursorLine,
  gridProps,
  lineProps,
  seriesColor,
} from "@/components/ds/charts";
import { EmptyState, KeyValues, MetricStrip, Notice, Panel, Segmented, SkeletonRows, StatusPill, type ChipOption } from "@/components/ds/kit";
import { api } from "@/services/api";
import type { DataStoreKpi, DataStoreWindow } from "@/types/dataStores";

import { ChartBody, ConnectionPill, MetricStripSkeleton, RefreshButton, SectionHeader, stripColumns } from "./parts";

const WINDOWS: ChipOption<DataStoreWindow>[] = [
  { value: "1h", label: "Last 1h" },
  { value: "24h", label: "Last 24h" },
  { value: "7d", label: "Last 7 days" },
];

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
  const timeOf = (idx: unknown) => points[Number(idx)]?.time ?? "";
  const kpis = data?.kpis ?? [];
  const recent = data?.recent_queries || [];

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Athena Database"
        description="Glue catalog and Athena workgroup used for archived job search. Read/write comes from SELECT vs INSERT/CTAS/UNLOAD executions. Page load does not start a new query."
        meta={
          <>
            <ConnectionPill loading={isLoading} connected={data?.connected} />
            {data?.ping_ms != null && <span className="num text-sm text-muted-foreground">{data.ping_ms} ms</span>}
          </>
        }
        actions={
          <>
            <Segmented options={WINDOWS} value={window} onChange={setWindow} label="Athena window" />
            <RefreshButton
              spinning={isFetching}
              disabled={isLoading}
              onClick={() => qc.invalidateQueries({ queryKey: ["athena-monitoring", window] })}
            >
              Refresh Status
            </RefreshButton>
          </>
        }
      />

      {data?.points_scope === "recent" ? (
        <Notice tone="neutral">Showing last workgroup executions (none in this window)</Notice>
      ) : null}

      {isLoading ? (
        <MetricStripSkeleton count={4} />
      ) : kpis.length > 0 ? (
        <MetricStrip
          columns={stripColumns(kpis.length)}
          items={kpis.map((kpi) => ({ label: kpi.label, value: formatKpi(kpi) }))}
        />
      ) : null}

      <div className="grid gap-6 xl:grid-cols-2">
        <Panel title="Read / write query trend">
          <ChartBody loading={isLoading} empty={!hasTrend && "No Athena query executions to chart yet."}>
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
                <YAxis yAxisId="count" allowDecimals={false} {...axisProps} width={36} />
                <YAxis yAxisId="bytes" orientation="right" {...axisProps} width={64} tickFormatter={(v) => formatBytes(v)} />
                <Tooltip
                  cursor={cursorBand}
                  content={
                    <ChartTooltip
                      labelFormatter={timeOf}
                      valueFormatter={(value, name) =>
                        name === "Data scanned" ? formatBytes(value as number) : value != null ? Number(value) : "—"
                      }
                    />
                  }
                />
                <Bar yAxisId="count" dataKey="read_queries" name="Read queries" fill={seriesColor(0)} {...barProps} maxBarSize={14} />
                <Bar yAxisId="count" dataKey="write_queries" name="Write queries" fill={seriesColor(1)} {...barProps} maxBarSize={14} />
                <Line yAxisId="bytes" dataKey="bytes_scanned" name="Data scanned" stroke={seriesColor(2)} {...lineProps} connectNulls />
              </ComposedChart>
            </ResponsiveContainer>
            <ChartLegend
              className="mt-3"
              items={[
                { label: "Read", color: seriesColor(0) },
                { label: "Write", color: seriesColor(1) },
                { label: "Scanned (right axis)", color: seriesColor(2) },
              ]}
            />
          </ChartBody>
        </Panel>

        <Panel title="Engine time">
          <ChartBody loading={isLoading} empty={!hasTrend && "No engine-time samples yet."}>
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
                <YAxis {...axisProps} width={56} tickFormatter={(v) => `${v} ms`} />
                <Tooltip
                  cursor={cursorLine}
                  content={
                    <ChartTooltip
                      labelFormatter={timeOf}
                      valueFormatter={(value) => (value != null ? `${Number(value).toFixed(0)} ms` : "—")}
                    />
                  }
                />
                <Line dataKey="avg_engine_ms" name="Avg engine" stroke={seriesColor(0)} {...lineProps} connectNulls />
              </ComposedChart>
            </ResponsiveContainer>
            <ChartLegend className="mt-3" items={[{ label: "Avg engine", color: seriesColor(0) }]} />
          </ChartBody>
        </Panel>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Panel title="Connection">
          <KeyValues
            items={[
              { label: "Region", value: data?.region || "—" },
              {
                label: "Glue / Athena",
                value: (
                  <span className="inline-flex items-center gap-2">
                    <StatusPill status={data?.glue_reachable ? "up" : "down"} />
                    <span className="text-subtle-foreground">/</span>
                    <StatusPill status={data?.athena_reachable ? "up" : "down"} />
                  </span>
                ),
              },
              { label: "Database", value: data?.database || "—" },
              { label: "Workgroup", value: data?.workgroup || "—" },
            ]}
          />
        </Panel>

        <Panel
          title="Archived jobs table"
          footer={<>Glue table {table?.name || "archived_jobs"} used when Dynamo job history is archived.</>}
        >
          <KeyValues
            items={[
              { label: "Exists", value: table?.exists ? "yes" : "no" },
              { label: "Partitions", value: `${table?.partition_count ?? "—"}${table?.partitions_truncated ? "+" : ""}` },
              { label: "Record count", value: table?.record_count ?? "—" },
              { label: "Archive bucket", value: data?.archive_bucket || "—" },
            ]}
          />
          {table?.location ? (
            <div className="mt-3 break-all font-mono text-xs text-muted-foreground">{table.location}</div>
          ) : null}
        </Panel>
      </div>

      <Panel
        title="Recent Athena queries"
        flush
        footer="Last executions in this workgroup. Page load does not start a new query."
      >
        {isLoading ? (
          <SkeletonRows rows={3} />
        ) : recent.length === 0 ? (
          <EmptyState bare icon="database" title="No recent query executions." />
        ) : (
          <div className="scroll-thin overflow-x-auto">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Query</th>
                  <th>Kind</th>
                  <th>State</th>
                  <th className="r">Engine time</th>
                  <th className="r">Scanned</th>
                </tr>
              </thead>
              <tbody>
                {recent.map((q) => (
                  <tr key={q.id}>
                    <td className="break-all font-mono text-xs text-foreground">{q.id}</td>
                    <td className="text-muted-foreground">{q.kind || "—"}</td>
                    <td>{q.state ? <StatusPill status={q.state} /> : "—"}</td>
                    <td className="r num whitespace-nowrap">{q.engine_ms != null ? `${q.engine_ms} ms` : "—"}</td>
                    <td className="r num whitespace-nowrap">{q.bytes_scanned_human || "—"}</td>
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
