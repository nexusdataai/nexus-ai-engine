import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Icon } from "@/components/ds/Icon";
import { EmptyState, Field, InlineError, Modal, Notice, Panel, SkeletonRows, StatusPill } from "@/components/ds/kit";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
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
  INTERVAL_PRESETS.map((p) => [p.value, p.label]),
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

/** On / off switch. Same behaviour as a checkbox, clearer for "enabled". */
function Switch({ checked, disabled, onChange, label }: { checked: boolean; disabled?: boolean; onChange: () => void; label: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={onChange}
      className={cn(
        "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full border transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:opacity-50",
        checked ? "border-primary bg-primary" : "border-border-strong bg-surface-3",
      )}
    >
      <span className={cn("inline-block h-3.5 w-3.5 rounded-full bg-white shadow-xs transition-transform duration-200 ease-brand", checked ? "translate-x-[18px]" : "translate-x-0.5")} />
    </button>
  );
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
  const enabledCount = rows.filter((s) => s.enabled).length;

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
    <Panel
      title="Batch Schedules"
      description={rows.length > 0 ? `${enabledCount} of ${rows.length} enabled` : undefined}
      flush
      actions={
        <>
          <Button variant="ghost" size="icon-sm" aria-label="Refresh schedules" onClick={() => refetch()} disabled={isFetching}>
            <Icon name="refresh" className={isFetching ? "animate-spin" : undefined} />
          </Button>
          <Button size="sm" onClick={() => setDialog({ mode: "create" })}>
            <Icon name="plus" />
            Create Schedule
          </Button>
        </>
      }
    >
      {isLoading ? (
        <SkeletonRows rows={4} />
      ) : error ? (
        <div className="p-4 sm:p-5">
          <InlineError onRetry={() => refetch()}>Could not load schedules. {String(error)}</InlineError>
        </div>
      ) : rows.length === 0 ? (
        <EmptyState bare icon="calendar" title="No batch schedules configured" description="Create a schedule to run this journey on an interval." />
      ) : (
        <div className="scroll-thin overflow-x-auto">
          <table className="tbl">
            <thead>
              <tr>
                <th>Journey / Stage</th>
                <th>Interval</th>
                <th>Last Run</th>
                <th>Next Run</th>
                <th>Status</th>
                <th className="r">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((s) => (
                <tr key={s.scheduleId}>
                  <td className="max-w-[320px]">
                    <div className="truncate font-medium text-foreground">{labelFor(s.journeyId)}</div>
                    <div className="truncate text-xs text-muted-foreground">{s.stageId || "All stages"}</div>
                  </td>
                  <td className="whitespace-nowrap">{formatInterval(s.intervalMinutes)}</td>
                  <td>
                    <div className="whitespace-nowrap text-muted-foreground">{formatTime(s.lastRunAt)}</div>
                    {s.lastJobStatus ? <StatusPill status={s.lastJobStatus} className="mt-0.5" /> : null}
                  </td>
                  <td className="whitespace-nowrap">
                    {s.enabled ? (
                      <span className="inline-flex items-center gap-1.5">
                        <Icon name="clock" className="h-3.5 w-3.5 text-subtle-foreground" />
                        {formatTime(s.nextRunAt)}
                      </span>
                    ) : (
                      <span className="text-subtle-foreground">Paused</span>
                    )}
                  </td>
                  <td>
                    <Switch
                      label={`${s.enabled ? "Pause" : "Enable"} schedule for ${labelFor(s.journeyId)}`}
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
                  <td>
                    <div className="flex items-center justify-end gap-1">
                      <Button
                        variant="outline"
                        size="sm"
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
                        <Icon name={runningNow === s.scheduleId ? "spinner" : "play"} className={runningNow === s.scheduleId ? "animate-spin" : undefined} />
                        Run Now
                      </Button>
                      <Button variant="ghost" size="icon-sm" aria-label="Edit schedule" title="Edit" onClick={() => setDialog({ mode: "edit", schedule: s })}>
                        <Icon name="edit" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label="Delete schedule"
                        title="Delete"
                        className="hover:text-destructive"
                        onClick={() => {
                          if (window.confirm(`Delete the schedule for "${labelFor(s.journeyId)}"?`)) remove.mutate(s.scheduleId);
                        }}
                      >
                        <Icon name="trash" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

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
    </Panel>
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

  const journeyLabel = journeys.find((j) => j.journeyId === journeyId)?.name;

  return (
    <Modal
      open
      onClose={onClose}
      className="max-w-lg"
      title={isEdit ? "Edit Batch Schedule" : "Create Batch Schedule"}
      description={
        journeyLabel
          ? `Schedule periodic execution for "${journeyLabel}"`
          : "Timezone is stored only. Jobs fire on UTC."
      }
      footer={
        <>
          <Button variant="outline" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={() => void handleSave()} disabled={saving}>
            {saving ? <Icon name="spinner" className="animate-spin" /> : null}
            {isEdit ? "Update" : "Create Schedule"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {!lockedJourneyId ? (
          <Field label="Journey" htmlFor="sched-journey">
            <select
              id="sched-journey"
              className="field"
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
          </Field>
        ) : null}
        <Field label="Stage (optional)" htmlFor="sched-stage">
          <select
            id="sched-stage"
            className="field"
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
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Run Interval" htmlFor="sched-interval">
            <select
              id="sched-interval"
              className="field"
              value={intervalMinutes}
              onChange={(e) => setIntervalMinutes(e.target.value)}
            >
              {INTERVAL_PRESETS.map((preset) => (
                <option key={preset.value} value={preset.value}>
                  {preset.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Timezone" htmlFor="sched-tz" hint="Stored only. Jobs fire on UTC.">
            <select
              id="sched-tz"
              className="field"
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
            >
              {TIMEZONES.map((tz) => (
                <option key={tz} value={tz}>
                  {tz}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <div className="flex items-center justify-between gap-4 border-t border-border pt-4 text-sm">
          <span className="text-foreground">
            Enabled
            <span className="block text-xs text-muted-foreground">Start scheduling immediately</span>
          </span>
          <Switch label="Enabled" checked={enabled} onChange={() => setEnabled((v) => !v)} />
        </div>
        {enabled && nextRunPreview ? (
          <Notice tone="neutral">First run approximately at {nextRunPreview}</Notice>
        ) : null}
        {error ? <InlineError>{error}</InlineError> : null}
      </div>
    </Modal>
  );
}
