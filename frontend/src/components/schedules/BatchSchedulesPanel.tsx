import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Calendar, Clock, Loader2, Pencil, Play, Plus, RefreshCw, Trash2 } from "lucide-react";

import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/services/api";
import type { ScheduleRow, SimpleJourneySummary } from "@/types/api";

const INTERVAL_PRESETS = [
  { value: 5, label: "Every 5 minutes" },
  { value: 10, label: "Every 10 minutes" },
  { value: 15, label: "Every 15 minutes" },
  { value: 30, label: "Every 30 minutes" },
  { value: 60, label: "Every hour" },
  { value: 360, label: "Every 6 hours" },
  { value: 1440, label: "Daily" },
];

const TIMEZONES = [
  "UTC",
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "Europe/London",
  "Europe/Berlin",
  "Asia/Singapore",
  "Asia/Tokyo",
  "Australia/Sydney",
];

const INTERVAL_LABELS: Record<number, string> = Object.fromEntries(
  INTERVAL_PRESETS.map((p) => [p.value, p.label.replace("Every ", "")]),
);

function formatInterval(minutes: number): string {
  return INTERVAL_LABELS[minutes] || `Every ${minutes}m`;
}

function formatTime(iso?: string | null): string {
  if (!iso) return "-";
  try {
    return new Date(iso).toLocaleString([], {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "-";
  }
}

function statusColor(status?: string | null): string {
  switch (status) {
    case "in_progress":
      return "bg-blue-100 text-blue-700";
    case "completed":
      return "bg-green-100 text-green-700";
    case "failed":
      return "bg-red-100 text-red-700";
    default:
      return "bg-muted text-muted-foreground";
  }
}

type DialogState = { mode: "create" } | { mode: "edit"; schedule: ScheduleRow } | null;

export type ScheduleStageOption = { id: string; name: string };

export function BatchSchedulesPanel({
  journeyId,
  journeyName,
  stages,
}: {
  journeyId?: string;
  journeyName?: string;
  stages?: ScheduleStageOption[];
}) {
  const queryClient = useQueryClient();
  const [dialog, setDialog] = useState<DialogState>(null);
  const [toggling, setToggling] = useState<string | null>(null);
  const [runningNow, setRunningNow] = useState<string | null>(null);

  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["schedules", journeyId ?? "all"],
    queryFn: () => api.listSchedules(journeyId),
  });
  const { data: journeys = [] } = useQuery({
    queryKey: ["simple-journeys"],
    queryFn: () => api.listSimpleJourneys(),
    enabled: !journeyId,
  });

  const rows = data?.data ?? [];
  const anyEnabled = rows.some((s) => s.enabled);

  useEffect(() => {
    if (!anyEnabled) return;
    const id = window.setInterval(() => {
      void queryClient.invalidateQueries({ queryKey: ["schedules"] });
    }, 30_000);
    return () => window.clearInterval(id);
  }, [anyEnabled, queryClient]);

  const toggle = useMutation({
    mutationFn: (id: string) => api.toggleSchedule(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["schedules"] }),
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.deleteSchedule(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["schedules"] }),
  });
  const runNow = useMutation({
    mutationFn: (id: string) => api.runScheduleNow(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["schedules"] }),
  });

  const labelFor = (id: string) =>
    journeyName && id === journeyId ? journeyName : journeys.find((j) => j.journeyId === id)?.name || id;

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <Calendar className="h-4 w-4" />
            Batch Schedules
          </CardTitle>
          <div className="flex items-center gap-1">
            <Button size="sm" variant="outline" onClick={() => setDialog({ mode: "create" })}>
              <Plus className="h-3 w-3" />
              Create Schedule
            </Button>
            <Button variant="ghost" size="sm" onClick={() => refetch()} disabled={isFetching}>
              <RefreshCw className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`} />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : error ? (
          <EmptyState title="Could not load schedules" description={String(error)} />
        ) : rows.length === 0 ? (
          <EmptyState title="No batch schedules configured" description="Create a schedule to run this journey on an interval." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-muted-foreground">
                  <th className="pb-2 pr-4 font-medium">Journey / Stage</th>
                  <th className="pb-2 pr-4 font-medium">Interval</th>
                  <th className="pb-2 pr-4 font-medium">Last Run</th>
                  <th className="pb-2 pr-4 font-medium">Next Run</th>
                  <th className="pb-2 pr-4 font-medium">Status</th>
                  <th className="pb-2 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((s) => (
                  <tr key={s.scheduleId} className="border-b border-border/50 last:border-0">
                    <td className="py-3 pr-4">
                      <div className="font-medium">{labelFor(s.journeyId)}</div>
                      <div className="text-xs text-muted-foreground">{s.stageId || "All stages"}</div>
                    </td>
                    <td className="py-3 pr-4">
                      <span className="inline-flex rounded-full border px-2 py-0.5 text-xs">
                        {formatInterval(s.intervalMinutes)}
                      </span>
                    </td>
                    <td className="py-3 pr-4 text-xs">
                      <div>{formatTime(s.lastRunAt)}</div>
                      {s.lastJobStatus ? (
                        <span className={`mt-0.5 inline-flex rounded-full px-2 py-0.5 text-[10px] font-medium ${statusColor(s.lastJobStatus)}`}>
                          {s.lastJobStatus}
                        </span>
                      ) : null}
                    </td>
                    <td className="py-3 pr-4 text-xs">
                      {s.enabled ? (
                        <span className="inline-flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {formatTime(s.nextRunAt)}
                        </span>
                      ) : (
                        <span className="text-muted-foreground">Paused</span>
                      )}
                    </td>
                    <td className="py-3 pr-4">
                      <input
                        type="checkbox"
                        checked={s.enabled}
                        disabled={toggling === s.scheduleId}
                        onChange={async () => {
                          setToggling(s.scheduleId);
                          try {
                            await toggle.mutateAsync(s.scheduleId);
                          } finally {
                            setToggling(null);
                          }
                        }}
                      />
                    </td>
                    <td className="py-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 px-2 text-xs text-green-700"
                          disabled={runningNow === s.scheduleId}
                          onClick={async () => {
                            setRunningNow(s.scheduleId);
                            try {
                              await runNow.mutateAsync(s.scheduleId);
                            } finally {
                              setRunningNow(null);
                            }
                          }}
                        >
                          {runningNow === s.scheduleId ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Play className="h-3.5 w-3.5" />
                          )}
                          Run Now
                        </Button>
                        <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => setDialog({ mode: "edit", schedule: s })}>
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 w-7 p-0 text-red-500"
                          onClick={() => remove.mutate(s.scheduleId)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>

      {dialog ? (
        <ScheduleDialog
          journeys={
            journeyId
              ? [{ journeyId, name: journeyName || journeyId, status: "pending" } satisfies SimpleJourneySummary]
              : journeys
          }
          lockedJourneyId={journeyId}
          stages={stages}
          existing={dialog.mode === "edit" ? dialog.schedule : undefined}
          onClose={() => setDialog(null)}
          onSaved={() => {
            setDialog(null);
            void queryClient.invalidateQueries({ queryKey: ["schedules"] });
          }}
        />
      ) : null}
    </Card>
  );
}

function ScheduleDialog({
  journeys,
  lockedJourneyId,
  stages: providedStages,
  existing,
  onClose,
  onSaved,
}: {
  journeys: SimpleJourneySummary[];
  lockedJourneyId?: string;
  stages?: ScheduleStageOption[];
  existing?: ScheduleRow;
  onClose: () => void;
  onSaved: () => void;
}) {
  const isEdit = !!existing;
  const [journeyId, setJourneyId] = useState(existing?.journeyId || lockedJourneyId || journeys[0]?.journeyId || "");
  const [stageId, setStageId] = useState(existing?.stageId || "");
  const [intervalMinutes, setIntervalMinutes] = useState(String(existing?.intervalMinutes || 5));
  const [timezone, setTimezone] = useState(existing?.timezone || "UTC");
  const [enabled, setEnabled] = useState(existing?.enabled ?? true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: journeyDetail } = useQuery({
    queryKey: ["stage-journey", journeyId],
    queryFn: () => api.getStageJourney(journeyId),
    enabled: !!journeyId && !isEdit && !providedStages,
  });

  const stages = providedStages ?? journeyDetail?.stages ?? [];
  const nextRunPreview = useMemo(() => {
    const minutes = Number(intervalMinutes);
    if (!enabled || !minutes) return "";
    return new Date(Date.now() + minutes * 60 * 1000).toLocaleTimeString();
  }, [enabled, intervalMinutes]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      if (isEdit && existing) {
        await api.updateSchedule(existing.scheduleId, {
          interval_minutes: Number(intervalMinutes),
          enabled,
          timezone,
        });
      } else {
        if (!journeyId) {
          setError("Select a journey");
          return;
        }
        await api.createSchedule({
          journey_id: journeyId,
          stage_id: stageId || undefined,
          interval_minutes: Number(intervalMinutes),
          enabled,
          timezone,
        });
      }
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div className="w-full max-w-lg rounded-lg border bg-background shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="border-b px-6 py-4">
          <h3 className="flex items-center gap-2 text-lg font-semibold">
            <Calendar className="h-5 w-5" />
            {isEdit ? "Edit Batch Schedule" : "Create Batch Schedule"}
          </h3>
          <p className="text-sm text-muted-foreground">
            {journeys.find((j) => j.journeyId === journeyId)?.name
              ? `Schedule periodic execution for "${journeys.find((j) => j.journeyId === journeyId)?.name}"`
              : "Timezone is stored only. Jobs fire on UTC."}
          </p>
        </div>
        <div className="space-y-4 px-6 py-4">
          {!lockedJourneyId ? (
            <label className="block space-y-1 text-sm">
              <span>Journey</span>
              <select
                className="h-9 w-full rounded-md border bg-background px-2"
                value={journeyId}
                disabled={isEdit}
                onChange={(e) => {
                  setJourneyId(e.target.value);
                  setStageId("");
                }}
              >
                {journeys.map((j) => (
                  <option key={j.journeyId} value={j.journeyId}>
                    {j.name}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <label className="block space-y-1 text-sm">
            <span>Stage (optional)</span>
            <select
              className="h-9 w-full rounded-md border bg-background px-2"
              value={stageId}
              disabled={isEdit}
              onChange={(e) => setStageId(e.target.value)}
            >
              <option value="">All stages (journey-level)</option>
              {stages.map((stage) => (
                <option key={stage.id} value={stage.id}>
                  {stage.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block space-y-1 text-sm">
            <span>Run Interval</span>
            <select
              className="h-9 w-full rounded-md border bg-background px-2"
              value={intervalMinutes}
              onChange={(e) => setIntervalMinutes(e.target.value)}
            >
              {INTERVAL_PRESETS.map((preset) => (
                <option key={preset.value} value={preset.value}>
                  {preset.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block space-y-1 text-sm">
            <span>Timezone</span>
            <select
              className="h-9 w-full rounded-md border bg-background px-2"
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
            >
              {TIMEZONES.map((tz) => (
                <option key={tz} value={tz}>
                  {tz}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center justify-between text-sm">
            <span>
              Enabled
              <span className="block text-xs text-muted-foreground">Start scheduling immediately</span>
            </span>
            <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
          </label>
          {enabled && nextRunPreview ? (
            <div className="flex items-center gap-2 rounded-md border p-3 text-sm text-muted-foreground">
              <Clock className="h-4 w-4" />
              First run approximately at {nextRunPreview}
            </div>
          ) : null}
          {error ? <p className="text-sm text-red-600">{error}</p> : null}
        </div>
        <div className="flex justify-end gap-2 border-t px-6 py-4">
          <Button variant="outline" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={() => void handleSave()} disabled={saving}>
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {isEdit ? "Update" : "Create Schedule"}
          </Button>
        </div>
      </div>
    </div>
  );
}
