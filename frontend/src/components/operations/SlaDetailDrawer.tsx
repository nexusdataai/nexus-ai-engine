import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { api } from "@/services/api";
import type { SlaComponent, SlaPillarId, SlaStatus } from "@/types/monitoring";
import { SLA_PILLAR_LABELS } from "@/types/monitoring";

const statusClass = (s?: SlaStatus) => {
  if (s === "healthy") return "bg-green-600 text-white";
  if (s === "warning") return "bg-yellow-600 text-white";
  if (s === "critical") return "bg-red-600 text-white";
  return "bg-gray-500 text-white";
};

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
    return <p className="text-sm text-muted-foreground py-4">No component data available.</p>;
  }
  return (
    <div className="space-y-3">
      {components.map((comp) => (
        <div key={comp.id} className="rounded-lg border p-3 space-y-2">
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-medium">{comp.label}</span>
            <span className={`rounded-full px-2 py-0.5 text-xs ${statusClass(comp.status)}`}>
              {comp.status ?? "unknown"}
            </span>
          </div>
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>{formatValue(comp)}</span>
            <span>Score: {comp.score != null ? comp.score.toFixed(0) : "—"}</span>
          </div>
          {comp.score != null ? (
            <div className="h-2 w-full rounded bg-muted">
              <div
                className="h-2 rounded bg-primary"
                style={{ width: `${Math.min(100, Math.max(0, comp.score))}%` }}
              />
            </div>
          ) : null}
        </div>
      ))}
    </div>
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
    <div className="fixed inset-0 z-50 flex justify-end">
      <button
        type="button"
        className="absolute inset-0 bg-black/50"
        aria-label="Close pillar details"
        onClick={() => onOpenChange(false)}
      />
      <aside className="relative h-full w-full max-w-lg overflow-y-auto border-l bg-background p-6 shadow-xl">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="flex items-center gap-2 text-lg font-semibold">
              {title}
              {detail?.status ? (
                <span className={`rounded-full px-2 py-0.5 text-xs ${statusClass(detail.status)}`}>
                  {detail.status}
                </span>
              ) : null}
            </h3>
            <p className="text-sm text-muted-foreground mt-1">
              {detail?.headline ?? "App and data layer component breakdown"}
            </p>
          </div>
          <Button variant="ghost" size="icon" onClick={() => onOpenChange(false)} aria-label="Close">
            <X className="h-4 w-4" />
          </Button>
        </div>

        {isLoading ? (
          <p className="py-12 text-sm text-muted-foreground">Loading…</p>
        ) : detail?.error ? (
          <p className="py-4 text-sm text-red-500">{detail.error}</p>
        ) : detail ? (
          <div className="mt-4 space-y-4">
            <div className="text-3xl font-bold">
              {detail.score != null ? `${detail.score.toFixed(1)}%` : "—"}
            </div>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                className={`rounded-md px-3 py-2 text-sm font-medium ${layer === "app" ? "bg-primary text-primary-foreground" : "bg-muted"}`}
                onClick={() => setLayer("app")}
              >
                App Layer
                {detail.app_layer?.score != null ? ` (${detail.app_layer.score.toFixed(0)})` : ""}
              </button>
              <button
                type="button"
                className={`rounded-md px-3 py-2 text-sm font-medium ${layer === "data" ? "bg-primary text-primary-foreground" : "bg-muted"}`}
                onClick={() => setLayer("data")}
              >
                Data Layer
                {detail.data_layer?.score != null ? ` (${detail.data_layer.score.toFixed(0)})` : ""}
              </button>
            </div>
            <ComponentRows
              components={layer === "app" ? detail.app_layer?.components : detail.data_layer?.components}
            />
            {detail.timeline && detail.timeline.length > 0 ? (
              <div className="space-y-2">
                <h4 className="text-sm font-medium">24h trend</h4>
                <div className="flex h-16 items-end gap-0.5">
                  {detail.timeline.slice(-48).map((pt) => (
                    <div
                      key={pt.timestamp}
                      className="min-h-[2px] flex-1 rounded-t bg-primary/70"
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
      </aside>
    </div>
  );
}
