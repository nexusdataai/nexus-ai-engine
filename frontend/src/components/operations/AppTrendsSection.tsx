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
  STATUS_COLORS,
  axisProps,
  barProps,
  cursorBand,
  gridProps,
  lineProps,
  seriesColor,
} from "@/components/ds/charts";
import { MetricStrip, Panel, Segmented, type ChipOption, type Metric } from "@/components/ds/kit";
import { api } from "@/services/api";
import type { AppTrendKpi, AppTrendsTab, AppTrendsWindow } from "@/types/appTrends";
import { useState } from "react";

import { ChartBody, MetricStripSkeleton, RefreshButton, SectionHeader, stripColumns } from "./parts";

const WINDOWS: ChipOption<AppTrendsWindow>[] = [
  { value: "24h", label: "Last 24h" },
  { value: "7d", label: "Last 7 days" },
  { value: "30d", label: "Last 30 days" },
];

/** Outcome series keep their status colour; everything else uses the blue scale. */
const OUTCOME_COLOR: Record<string, string> = {
  succeeded: STATUS_COLORS.success,
  success: STATUS_COLORS.success,
  completed: STATUS_COLORS.success,
  failed: STATUS_COLORS.danger,
  last_failed: STATUS_COLORS.danger,
  error: STATUS_COLORS.danger,
};

/** Assign one colour per id: status colour for outcomes, otherwise the next series hue. */
function paletteFor(ids: string[]): Record<string, string> {
  const out: Record<string, string> = {};
  let next = 0;
  for (const id of ids) {
    if (out[id]) continue;
    out[id] = OUTCOME_COLOR[id] ?? seriesColor(next++);
  }
  return out;
}

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
  const mix = data?.mix ?? [];
  const mixTotal = mix.reduce((n, m) => n + (m.value || 0), 0);
  const countSeries = (data?.series ?? []).filter((s) => s.axis === "count" && s.id !== "rate");
  const rateSeries = (data?.series ?? []).find((s) => s.axis === "percent");

  const colors = paletteFor([...countSeries.map((s) => s.id), "rate"]);
  const mixColors = { ...paletteFor(mix.map((m) => m.id)), ...Object.fromEntries(mix.filter((m) => colors[m.id]).map((m) => [m.id, colors[m.id]])) };
  const showMix = mix.length > 0 && mixTotal > 0;

  const kpis = data?.kpis ?? [];
  const kpiItems: Metric[] = kpis.map((kpi) => ({
    label: kpi.label,
    value: formatKpi(kpi),
    tone: (kpi.id === "failed" || kpi.id === "last_failed") && Number(kpi.value) > 0 ? "danger" : undefined,
  }));

  return (
    <div className="space-y-6">
      <SectionHeader
        title={<>{tab === "executions" ? "Executions" : tab === "queue" ? "Queue" : "Schedules"} trends</>}
        description={data?.chart_title ?? "Volume over time with a quality/rate overlay."}
        actions={
          <>
            <Segmented options={WINDOWS} value={window} onChange={setWindow} label="Trend window" />
            <RefreshButton
              spinning={isFetching}
              onClick={() => qc.invalidateQueries({ queryKey: ["app-trends", tab, window] })}
            >
              Refresh
            </RefreshButton>
          </>
        }
      />

      {isLoading ? (
        <MetricStripSkeleton count={6} />
      ) : kpiItems.length > 0 ? (
        <MetricStrip items={kpiItems} columns={stripColumns(kpiItems.length)} />
      ) : null}

      <div className={showMix ? "grid gap-6 xl:grid-cols-[minmax(0,1fr)_300px]" : undefined}>
        <Panel title={data?.chart_title ?? "Trend"}>
          <ChartBody
            loading={isLoading}
            error={data?.error}
            empty={points.length === 0 && "No trend data yet for this window."}
            height={280}
          >
            <ResponsiveContainer width="100%" height={280}>
              <ComposedChart data={points} margin={CHART_MARGIN}>
                <CartesianGrid {...gridProps} />
                <XAxis dataKey="time" {...axisProps} interval="preserveStartEnd" />
                <YAxis yAxisId="count" {...axisProps} allowDecimals={false} width={40} />
                <YAxis
                  yAxisId="percent"
                  orientation="right"
                  domain={[0, 100]}
                  {...axisProps}
                  tickFormatter={(v) => `${v}%`}
                  width={44}
                />
                <Tooltip
                  cursor={cursorBand}
                  content={
                    <ChartTooltip
                      valueFormatter={(value, name) =>
                        value == null ? "—" : `${value}${rateSeries && name === rateSeries.label ? "%" : ""}`
                      }
                    />
                  }
                />
                {countSeries.map((s, i) => (
                  <Bar
                    key={s.id}
                    yAxisId="count"
                    dataKey={s.id}
                    name={s.label}
                    stackId="volume"
                    fill={colors[s.id]}
                    {...barProps}
                    radius={i === countSeries.length - 1 ? barProps.radius : 0}
                    maxBarSize={28}
                  />
                ))}
                {rateSeries ? (
                  <Line
                    yAxisId="percent"
                    dataKey="rate"
                    name={rateSeries.label}
                    stroke={colors.rate}
                    {...lineProps}
                    connectNulls
                  />
                ) : null}
              </ComposedChart>
            </ResponsiveContainer>
            <ChartLegend
              className="mt-3"
              items={[
                ...countSeries.map((s) => ({ label: s.label, color: colors[s.id] })),
                ...(rateSeries ? [{ label: `${rateSeries.label} (right axis)`, color: colors.rate }] : []),
              ]}
            />
          </ChartBody>
        </Panel>

        {showMix ? (
          <Panel title="Mix">
            <div className="flex h-2 w-full gap-0.5 overflow-hidden rounded-full">
              {mix.map((m) => (
                <div
                  key={m.id}
                  style={{
                    width: `${Math.max(0, (m.value / mixTotal) * 100)}%`,
                    backgroundColor: mixColors[m.id],
                  }}
                  title={`${m.label}: ${m.value}`}
                />
              ))}
            </div>
            <ul className="mt-4">
              {mix.map((m) => (
                <li key={m.id} className="flex items-center justify-between gap-3 border-b border-border py-2 text-sm last:border-b-0">
                  <span className="flex min-w-0 items-center gap-2 text-muted-foreground">
                    <span className="h-2 w-2 shrink-0 rounded-[2px]" style={{ backgroundColor: mixColors[m.id] }} aria-hidden="true" />
                    <span className="truncate">
                      {m.label} {((m.value / mixTotal) * 100).toFixed(0)}%
                    </span>
                  </span>
                  <span className="num shrink-0 font-medium text-foreground">{m.value}</span>
                </li>
              ))}
            </ul>
          </Panel>
        ) : null}
      </div>
    </div>
  );
}
