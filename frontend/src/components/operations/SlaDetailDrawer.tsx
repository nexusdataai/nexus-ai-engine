import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { DetailSheet, EmptyState, InlineError, Meter, Segmented, SkeletonRows, StatusPill, SubHeading } from "@/components/ds/kit";
import { api } from "@/services/api";
import type { SlaComponent, SlaPillarId } from "@/types/monitoring";
import { SLA_PILLAR_LABELS } from "@/types/monitoring";

import { healthTone } from "./parts";

function formatValue(comp: SlaComponent): string {
  if (comp.value == null) return "—";
  const v = comp.value;
  if (comp.unit === "ms" && v >= 1000) return `${(v / 1000).toFixed(1)}s`;
  if (comp.unit === "%") return `${v.toFixed(1)}%`;
  if (comp.unit === "req/s") return `${v.toFixed(1)} req/s`;
  if (comp.unit === "count") return String(Math.round(v));
  return `${v}${comp.unit ? ` ${comp.unit}` : ""}`;
}

function ComponentRows({ components }: { components?: SlaComponent[] }) {
  if (!components?.length) {
    return <EmptyState bare title="No component data available." className="py-6" />;
  }
  return (
    <ul className="divide-y divide-border border-y border-border">
      {components.map((comp) => (
        <li key={comp.id} className="space-y-2 py-3">
          <div className="flex items-center justify-between gap-2">
            <span className="min-w-0 truncate text-sm font-medium text-foreground">{comp.label}</span>
            <StatusPill tone={healthTone(comp.status)}>{comp.status ?? "unknown"}</StatusPill>
          </div>
          <div className="num flex items-center justify-between text-xs text-muted-foreground">
            <span>{formatValue(comp)}</span>
            <span>Score: {comp.score != null ? comp.score.toFixed(0) : "—"}</span>
          </div>
          {comp.score != null ? <Meter value={Math.min(100, Math.max(0, comp.score))} label={`${comp.label} score`} /> : null}
        </li>
      ))}
    </ul>
  );
}

export interface SlaDetailDrawerProps {
  pillar: SlaPillarId | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  window?: "1h" | "24h";
}

export function SlaDetailDrawer({
  pillar,
  open,
  onOpenChange,
  window: slaWindow = "1h",
}: SlaDetailDrawerProps) {
  const [layer, setLayer] = useState<"app" | "data">("app");
  const { data: detail, isLoading } = useQuery({
    queryKey: ["sla-pillar", pillar, slaWindow],
    queryFn: () => api.getSlaPillar(pillar as SlaPillarId, slaWindow),
    enabled: open && !!pillar,
  });

  if (!open || !pillar) return null;
  const title = SLA_PILLAR_LABELS[pillar];

  return (
    <DetailSheet
      open={open}
      onClose={() => onOpenChange(false)}
      title={title}
      description={detail?.headline ?? "App and data layer component breakdown"}
      meta={
        detail?.status ? (
          <StatusPill variant="soft" tone={healthTone(detail.status)}>
            {detail.status}
          </StatusPill>
        ) : undefined
      }
    >
      {isLoading ? (
        <SkeletonRows rows={5} className="p-0" />
      ) : detail?.error ? (
        <InlineError>{detail.error}</InlineError>
      ) : detail ? (
        <div className="space-y-5">
          <div className="num text-3xl font-medium tracking-tight text-foreground">
            {detail.score != null ? `${detail.score.toFixed(1)}%` : "—"}
          </div>
          <Segmented
            label="Layer"
            value={layer}
            onChange={setLayer}
            options={[
              {
                value: "app",
                label: `App Layer${detail.app_layer?.score != null ? ` (${detail.app_layer.score.toFixed(0)})` : ""}`,
              },
              {
                value: "data",
                label: `Data Layer${detail.data_layer?.score != null ? ` (${detail.data_layer.score.toFixed(0)})` : ""}`,
              },
            ]}
          />
          <ComponentRows
            components={layer === "app" ? detail.app_layer?.components : detail.data_layer?.components}
          />
          {detail.timeline && detail.timeline.length > 0 ? (
            <div>
              <SubHeading>24h trend</SubHeading>
              <div className="flex h-16 items-end gap-0.5">
                {detail.timeline.slice(-48).map((pt) => (
                  <div
                    key={pt.timestamp}
                    className="min-h-[2px] flex-1 rounded-t-sm bg-primary/70"
                    style={{
                      height: `${Math.max(4, (pt.score ?? 0) * 0.6)}%`,
                      opacity: pt.status === "critical" ? 0.5 : 1,
                    }}
                    title={`${new Date(pt.timestamp).toLocaleTimeString()}: ${pt.score?.toFixed(0) ?? "—"}%`}
                  />
                ))}
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
    </DetailSheet>
  );
}
