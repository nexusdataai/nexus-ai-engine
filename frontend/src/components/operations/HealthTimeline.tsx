import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { AreaFill, CHART_MARGIN, axisProps, cursorLine, gridProps, lineProps, seriesColor } from "@/components/ds/charts";
import { Panel, Segmented, StatusPill, type ChipOption } from "@/components/ds/kit";
import { api } from "@/services/api";

import { ChartBody, healthTone } from "./parts";

const STATUS_VALUE: Record<string, number> = {
  healthy: 3,
  degraded: 2,
  warning: 2,
  unhealthy: 1,
  critical: 1,
  unknown: 0,
};

type ChartMode = "score" | "status";

const MODES: ChipOption<ChartMode>[] = [
  { value: "score", label: "Score" },
  { value: "status", label: "Status" },
];

export function HealthTimeline({ window = "1h" }: { window?: "1h" | "24h" }) {
  const [mode, setMode] = useState<ChartMode>("score");
  const { data, isLoading } = useQuery({
    queryKey: ["sla-timeline", 24, window],
    queryFn: () => api.getSlaTimeline(24),
  });

  const chartData = (data?.points ?? []).map((p) => ({
    time: new Date(p.timestamp).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    }),
    score: p.overall_score ?? 0,
    status: STATUS_VALUE[p.overall_status ?? "unknown"] ?? 0,
    statusLabel: p.overall_status ?? "unknown",
  }));

  const latest = chartData.length > 0 ? chartData[chartData.length - 1] : null;
  const latestStatus = latest?.statusLabel ?? "unknown";
  const dataKey = mode === "score" ? "score" : "status";
  const color = seriesColor(0);

  return (
    <Panel
      title="SLA Timeline (24h)"
      actions={
        <>
          <StatusPill tone={healthTone(latestStatus)}>{latestStatus}</StatusPill>
          <Segmented options={MODES} value={mode} onChange={setMode} label="Timeline value" />
        </>
      }
    >
      <ChartBody
        loading={isLoading}
        empty={chartData.length === 0 && "No timeline data yet. Data appears after 5 minutes."}
        height={180}
      >
        <ResponsiveContainer width="100%" height={180}>
          <AreaChart data={chartData} margin={CHART_MARGIN}>
            <defs>
              <AreaFill id="sla-timeline-fill" color={color} />
            </defs>
            <CartesianGrid {...gridProps} />
            <XAxis dataKey="time" {...axisProps} interval="preserveStartEnd" />
            <YAxis
              {...axisProps}
              domain={mode === "score" ? [0, 100] : [0, 3]}
              ticks={mode === "score" ? [0, 50, 100] : [1, 2, 3]}
              tickFormatter={(v) => (mode === "score" ? `${v}%` : ["", "Bad", "Warn", "OK"][v] || "")}
              width={44}
            />
            <Tooltip
              cursor={cursorLine}
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const d = payload[0].payload;
                return (
                  <div className="min-w-[128px] space-y-1 rounded-lg border border-border-strong bg-popover px-3 py-2 text-xs text-popover-foreground shadow-md">
                    <div className="mb-1.5 font-medium text-foreground">{d.time}</div>
                    {mode === "score" && d.score != null && (
                      <div className="flex items-center justify-between gap-4">
                        <span className="text-muted-foreground">SLA Score</span>
                        <span className="num font-medium text-foreground">{Number(d.score).toFixed(1)}%</span>
                      </div>
                    )}
                    <div className="flex items-center justify-between gap-4">
                      <span className="text-muted-foreground">Status</span>
                      <StatusPill tone={healthTone(d.statusLabel)}>{d.statusLabel}</StatusPill>
                    </div>
                  </div>
                );
              }}
            />
            <Area {...lineProps} type="stepAfter" dataKey={dataKey} stroke={color} fill="url(#sla-timeline-fill)" />
          </AreaChart>
        </ResponsiveContainer>
      </ChartBody>
    </Panel>
  );
}
