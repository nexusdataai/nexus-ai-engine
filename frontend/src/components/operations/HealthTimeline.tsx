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

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/services/api";

const STATUS_VALUE: Record<string, number> = {
  healthy: 3,
  degraded: 2,
  warning: 2,
  unhealthy: 1,
  critical: 1,
  unknown: 0,
};

const STATUS_COLOR: Record<string, string> = {
  healthy: "#22c55e",
  degraded: "#eab308",
  warning: "#eab308",
  unhealthy: "#ef4444",
  critical: "#ef4444",
  unknown: "#6b7280",
};

type ChartMode = "score" | "status";

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

  return (
    <Card className="mt-4">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-sm">SLA Timeline (24h)</CardTitle>
          <div className="flex items-center gap-2">
            <div className="flex gap-1">
              <Button
                variant={mode === "score" ? "secondary" : "ghost"}
                size="sm"
                className="h-7 text-xs"
                onClick={() => setMode("score")}
              >
                Score
              </Button>
              <Button
                variant={mode === "status" ? "secondary" : "ghost"}
                size="sm"
                className="h-7 text-xs"
                onClick={() => setMode("status")}
              >
                Status
              </Button>
            </div>
            <span
              className="rounded-full px-2 py-0.5 text-xs font-medium"
              style={{
                backgroundColor: `${STATUS_COLOR[latestStatus] ?? "#6b7280"}20`,
                color: STATUS_COLOR[latestStatus] ?? "#6b7280",
              }}
            >
              {latestStatus}
            </span>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="h-[150px] flex items-center justify-center text-sm text-muted-foreground">
            Loading...
          </div>
        ) : chartData.length === 0 ? (
          <div className="h-[150px] flex items-center justify-center text-sm text-muted-foreground">
            No timeline data yet. Data appears after 5 minutes.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={150}>
            <AreaChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.1} />
              <XAxis dataKey="time" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis
                domain={mode === "score" ? [0, 100] : [0, 3]}
                ticks={mode === "score" ? [0, 50, 100] : [1, 2, 3]}
                tick={{ fontSize: 10 }}
                tickFormatter={(v) => (mode === "score" ? `${v}%` : ["", "Bad", "Warn", "OK"][v] || "")}
                width={40}
              />
              <Tooltip
                content={({ payload }) => {
                  if (!payload?.length) return null;
                  const d = payload[0].payload;
                  return (
                    <div className="bg-background border rounded p-2 text-xs shadow">
                      <div className="font-medium">{d.time}</div>
                      {mode === "score" && d.score != null && (
                        <div>SLA Score: {Number(d.score).toFixed(1)}%</div>
                      )}
                      <div>
                        Status:{" "}
                        <span style={{ color: STATUS_COLOR[d.statusLabel] }}>{d.statusLabel}</span>
                      </div>
                    </div>
                  );
                }}
              />
              <Area
                type="stepAfter"
                dataKey={dataKey}
                stroke="#3b82f6"
                fill="#3b82f680"
                strokeWidth={2}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
