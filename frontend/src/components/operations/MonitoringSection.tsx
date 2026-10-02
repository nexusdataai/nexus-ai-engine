import { useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, CheckCircle, Clock, Shield, Wifi } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/services/api";
import type { SlaPillar, SlaPillarId, SlaStatus } from "@/types/monitoring";
import { SLA_PILLAR_ORDER } from "@/types/monitoring";

import { HealthTimeline } from "./HealthTimeline";
import { SlaDetailDrawer } from "./SlaDetailDrawer";

export type SlaWindow = "1h" | "24h";

const PILLAR_ICONS: Record<SlaPillarId, ReactNode> = {
  performance: <Activity className="h-5 w-5" />,
  availability: <Wifi className="h-5 w-5" />,
  reliability: <CheckCircle className="h-5 w-5" />,
  security: <Shield className="h-5 w-5" />,
  compliance: <Clock className="h-5 w-5" />,
};

const LABELS: Record<SlaPillarId, string> = {
  performance: "Performance",
  availability: "Availability",
  reliability: "Reliability",
  security: "Security",
  compliance: "Compliance",
};

const statusClass = (s: string) =>
  s === "healthy"
    ? "bg-green-600 text-white"
    : s === "warning"
      ? "bg-yellow-600 text-white"
      : s === "unknown"
        ? "bg-gray-500 text-white"
        : "bg-red-600 text-white";

const normalizeStatus = (s?: string): SlaStatus => {
  if (s === "warning" || s === "critical" || s === "healthy" || s === "unknown") return s;
  return "unknown";
};

function pillarToCard(id: SlaPillarId, pillar: SlaPillar | undefined) {
  if (!pillar || pillar.score == null) {
    return {
      id,
      title: LABELS[id],
      icon: PILLAR_ICONS[id],
      value: "—",
      unit: "%",
      status: "unknown" as SlaStatus,
      details: [{ label: "Status", value: "No data" }],
    };
  }
  return {
    id,
    title: LABELS[id],
    icon: PILLAR_ICONS[id],
    value: String(Math.round(pillar.score * 10) / 10),
    unit: "%",
    status: normalizeStatus(pillar.status),
    details: pillar.summary_metrics?.map((m) => ({ label: m.label, value: m.value })) ?? [],
  };
}

export function MonitoringSection() {
  const [window, setWindow] = useState<SlaWindow>("1h");
  const [selectedPillar, setSelectedPillar] = useState<SlaPillarId | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["sla-summary", window],
    queryFn: () => api.getSlaSummary(window),
    refetchInterval: 60_000,
  });

  const overallScore = data?.overall_score ?? null;
  const overallStatus = normalizeStatus(data?.overall_status);
  const metrics = SLA_PILLAR_ORDER.map((id) => pillarToCard(id, data?.pillars?.[id]));

  const openPillar = (id: SlaPillarId) => {
    setSelectedPillar(id);
    setDrawerOpen(true);
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold">System Monitoring</h3>
          {!isLoading && overallScore != null ? (
            <p className="text-sm text-muted-foreground mt-0.5">
              Overall SLA:{" "}
              <span className="font-medium text-foreground">{overallScore.toFixed(1)}%</span>
              <span className={`ml-2 rounded-full px-2 py-0.5 text-xs ${statusClass(overallStatus)}`}>
                {overallStatus}
              </span>
            </p>
          ) : null}
        </div>
        <div className="flex items-center gap-2">
          <select
            className="h-8 rounded-md border bg-background px-2 text-xs"
            value={window}
            onChange={(e) => setWindow(e.target.value as SlaWindow)}
            aria-label="SLA window"
          >
            <option value="1h">Last 1h</option>
            <option value="24h">Last 24h</option>
          </select>
          <span className="rounded-full border px-2 py-0.5 text-xs">Live</span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {isLoading
          ? Array.from({ length: 5 }).map((_, i) => (
              <Card key={i}>
                <CardContent className="pt-6">
                  <div className="h-24 animate-pulse rounded bg-muted" />
                </CardContent>
              </Card>
            ))
          : metrics.map((m) => (
              <Card
                key={m.id}
                className="cursor-pointer transition-colors hover:border-primary/50"
                onClick={() => openPillar(m.id)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    openPillar(m.id);
                  }
                }}
              >
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center justify-between text-sm">
                    <span className="flex items-center gap-2">
                      {m.icon}
                      {m.title}
                    </span>
                    <span className={`rounded-full px-2 py-0.5 text-xs ${statusClass(m.status)}`}>
                      {m.status}
                    </span>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="mb-3 text-3xl font-bold">
                    {m.value}
                    <span className="text-lg text-muted-foreground">{m.unit}</span>
                  </div>
                  <div className="space-y-1">
                    {m.details.map((d) => (
                      <div key={d.label} className="flex justify-between text-xs text-muted-foreground">
                        <span>{d.label}</span>
                        <span className="font-medium">{d.value}</span>
                      </div>
                    ))}
                  </div>
                  <Button variant="ghost" size="sm" className="mt-2 h-7 w-full text-xs">
                    View details
                  </Button>
                </CardContent>
              </Card>
            ))}
      </div>

      <HealthTimeline window={window} />

      <SlaDetailDrawer
        pillar={selectedPillar}
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        window={window}
      />
    </div>
  );
}
