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
  cursorLine,
  gridProps,
  lineProps,
  seriesColor,
} from "@/components/ds/charts";
import { MetricStrip, Panel, Segmented, type ChipOption } from "@/components/ds/kit";
import { api } from "@/services/api";
import type { ResourceKpi, ResourceWindow } from "@/types/resourceMonitoring";

import { ChartBody, MetricStripSkeleton, RefreshButton, SectionHeader, stripColumns } from "./parts";

const WINDOWS: ChipOption<ResourceWindow>[] = [
  { value: "1h", label: "Last 1h" },
  { value: "24h", label: "Last 24h" },
  { value: "7d", label: "Last 7 days" },
];

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
  const timeOf = (idx: unknown) => points[Number(idx)]?.time ?? "";
  const kpis = data?.kpis ?? [];

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Resource Monitoring"
        description={<>Local K3s node usage{data?.node ? ` · ${data.node}` : ""} with running job count.</>}
        actions={
          <>
            <Segmented options={WINDOWS} value={window} onChange={setWindow} label="Resource window" />
            <RefreshButton
              spinning={isFetching}
              onClick={() => qc.invalidateQueries({ queryKey: ["resource-monitoring", window] })}
            >
              Refresh
            </RefreshButton>
          </>
        }
      />

      {isLoading ? (
        <MetricStripSkeleton count={5} />
      ) : kpis.length > 0 ? (
        <MetricStrip
          columns={stripColumns(kpis.length)}
          items={kpis.map((kpi) => ({ label: kpi.label, value: formatKpi(kpi) }))}
        />
      ) : null}

      <div className="grid gap-6 xl:grid-cols-2">
        <Panel title="CPU, memory, and storage">
          <ChartBody loading={isLoading} error={data?.error} empty={points.length === 0 && "No resource samples yet."}>
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
                <YAxis domain={[0, 100]} {...axisProps} tickFormatter={(v) => `${v}%`} width={44} />
                <Tooltip
                  cursor={cursorLine}
                  content={
                    <ChartTooltip
                      labelFormatter={timeOf}
                      valueFormatter={(value) => (value != null ? `${Number(value).toFixed(1)}%` : "—")}
                    />
                  }
                />
                <Line dataKey="cpu_pct" name="CPU" stroke={seriesColor(0)} {...lineProps} connectNulls />
                <Line dataKey="memory_pct" name="Memory" stroke={seriesColor(1)} {...lineProps} connectNulls />
                <Line dataKey="storage_pct" name="Storage" stroke={seriesColor(2)} {...lineProps} connectNulls />
              </ComposedChart>
            </ResponsiveContainer>
            <ChartLegend
              className="mt-3"
              items={[
                { label: "CPU %", color: seriesColor(0) },
                { label: "Memory %", color: seriesColor(1) },
                { label: "Storage %", color: seriesColor(2) },
              ]}
            />
          </ChartBody>
        </Panel>

        <Panel title="Network and running jobs">
          <ChartBody
            loading={isLoading}
            empty={points.length === 0 && "No network samples yet. Rates appear after a second scrape."}
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
                <YAxis yAxisId="net" {...axisProps} width={44} tickFormatter={(v) => `${v}`} />
                <YAxis yAxisId="jobs" orientation="right" allowDecimals={false} {...axisProps} width={36} />
                <Tooltip
                  cursor={cursorLine}
                  content={
                    <ChartTooltip
                      labelFormatter={timeOf}
                      valueFormatter={(value, name) =>
                        name === "Jobs running" ? Number(value ?? 0) : value != null ? Number(value).toFixed(3) : "—"
                      }
                    />
                  }
                />
                <Bar
                  yAxisId="jobs"
                  dataKey="jobs_running"
                  name="Jobs running"
                  fill={seriesColor(2)}
                  fillOpacity={0.45}
                  {...barProps}
                  maxBarSize={14}
                  minPointSize={0}
                />
                <Line yAxisId="net" dataKey="network_rx_mbps" name="Rx Mbps" stroke={seriesColor(0)} {...lineProps} connectNulls />
                <Line yAxisId="net" dataKey="network_tx_mbps" name="Tx Mbps" stroke={seriesColor(1)} {...lineProps} connectNulls />
              </ComposedChart>
            </ResponsiveContainer>
            <ChartLegend
              className="mt-3"
              items={[
                { label: "Rx Mbps", color: seriesColor(0) },
                { label: "Tx Mbps", color: seriesColor(1) },
                { label: "Jobs (right axis)", color: seriesColor(2) },
              ]}
            />
          </ChartBody>
        </Panel>
      </div>
    </div>
  );
}
