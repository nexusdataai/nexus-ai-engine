import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Icon } from "@/components/ds/Icon";
import { LiveBadge, Segmented, Skeleton, StatusPill, type ChipOption } from "@/components/ds/kit";
import { api } from "@/services/api";
import type { SlaPillar, SlaPillarId, SlaStatus } from "@/types/monitoring";
import { SLA_PILLAR_ORDER } from "@/types/monitoring";

import { HealthTimeline } from "./HealthTimeline";
import { SectionHeader, healthTone } from "./parts";
import { SlaDetailDrawer } from "./SlaDetailDrawer";

export type SlaWindow = "1h" | "24h";

const WINDOWS: ChipOption<SlaWindow>[] = [
  { value: "1h", label: "Last 1h" },
  { value: "24h", label: "Last 24h" },
];

const LABELS: Record<SlaPillarId, string> = {
  performance: "Performance",
  availability: "Availability",
  reliability: "Reliability",
  security: "Security",
  compliance: "Compliance",
};

const normalizeStatus = (s?: string): SlaStatus => {
  if (s === "warning" || s === "critical" || s === "healthy" || s === "unknown") return s;
  return "unknown";
};

function pillarToCard(id: SlaPillarId, pillar: SlaPillar | undefined) {
  if (!pillar || pillar.score == null) {
    return {
      id,
      title: LABELS[id],
      value: "—",
      unit: "%",
      status: "unknown" as SlaStatus,
      details: [{ label: "Status", value: "No data" }],
    };
  }
  return {
    id,
    title: LABELS[id],
    value: String(Math.round(pillar.score * 10) / 10),
    unit: "%",
    status: normalizeStatus(pillar.status),
    details: pillar.summary_metrics?.map((m) => ({ label: m.label, value: m.value })) ?? [],
  };
}

const CELL = "border-b border-r border-border p-4 sm:px-5";

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
    <div className="space-y-6">
      <SectionHeader
        title="System Monitoring"
        meta={
          !isLoading && overallScore != null ? (
            <StatusPill variant="soft" tone={healthTone(overallStatus)}>
              {overallStatus}
            </StatusPill>
          ) : null
        }
        description={
          !isLoading && overallScore != null ? (
            <>
              Overall SLA: <span className="num font-medium text-foreground">{overallScore.toFixed(1)}%</span>
            </>
          ) : null
        }
        actions={
          <>
            <LiveBadge live />
            <Segmented options={WINDOWS} value={window} onChange={setWindow} label="SLA window" />
          </>
        }
      />

      {/* One strip, divided by hairlines; each pillar opens its breakdown. */}
      <div className="overflow-hidden rounded-xl border border-border bg-card shadow-xs">
        <div className="-mb-px -mr-px grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-5">
          {isLoading
            ? Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className={CELL} aria-busy="true">
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="mt-3 h-7 w-16" />
                  <Skeleton className="mt-4 h-3 w-full" />
                  <Skeleton className="mt-2 h-3 w-2/3" />
                </div>
              ))
            : metrics.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => openPillar(m.id)}
                  className={`${CELL} group flex min-w-0 flex-col text-left transition-colors duration-150 hover:bg-surface-2/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring`}
                >
                  <span className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm text-muted-foreground">{m.title}</span>
                    <StatusPill tone={healthTone(m.status)}>{m.status}</StatusPill>
                  </span>
                  <span className="num mt-2 block text-2xl font-medium tracking-tight text-foreground">
                    {m.value}
                    <span className="ml-0.5 text-base text-muted-foreground">{m.unit}</span>
                  </span>
                  <span className="mt-3 block flex-1 space-y-1">
                    {m.details.map((d) => (
                      <span key={d.label} className="flex justify-between gap-3 text-xs">
                        <span className="truncate text-muted-foreground">{d.label}</span>
                        <span className="num truncate font-medium text-foreground">{d.value}</span>
                      </span>
                    ))}
                  </span>
                  <span className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-muted-foreground transition-colors group-hover:text-primary dark:group-hover:text-brand-hi">
                    View details
                    <Icon name="arrow-right" className="h-3 w-3" />
                  </span>
                </button>
              ))}
        </div>
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
