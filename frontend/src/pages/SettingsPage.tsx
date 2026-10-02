import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Layers, Save, Settings, Timer, Users } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/services/api";
import type { EngineSettings } from "@/types/api";

export function SettingsPage() {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({
    queryKey: ["settings"],
    queryFn: () => api.getSettings(),
  });

  return (
    <div className="space-y-4">
      <div>
        <h2 className="flex items-center gap-2 text-xl font-semibold">
          <Settings className="h-5 w-5" />
          Settings
        </h2>
        <p className="text-sm text-muted-foreground">
          Worker, queue, and scheduler settings for this ai-engine.
        </p>
      </div>
      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : error || !data ? (
        <p className="text-sm text-red-500">{error ? String(error) : "Could not load settings"}</p>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <WorkersCard
            settings={data}
            onSaved={() => qc.invalidateQueries({ queryKey: ["settings"] })}
          />
          <QueueCard
            settings={data}
            onSaved={() => qc.invalidateQueries({ queryKey: ["settings"] })}
          />
          <SchedulerCard
            settings={data}
            onSaved={() => qc.invalidateQueries({ queryKey: ["settings"] })}
          />
        </div>
      )}
    </div>
  );
}

function WorkersCard({
  settings,
  onSaved,
}: {
  settings: EngineSettings;
  onSaved: () => void;
}) {
  const w = settings.workers;
  const [replicas, setReplicas] = useState(w.replicas ?? 1);
  const [threads, setThreads] = useState(w.threads);
  const [autoOn, setAutoOn] = useState(w.autoscaling?.enabled ?? false);
  const [autoMin, setAutoMin] = useState(w.autoscaling?.min_replicas ?? 1);
  const [autoMax, setAutoMax] = useState(w.autoscaling?.max_replicas ?? 10);
  const [message, setMessage] = useState<string | null>(null);
  const lagTarget = 2 * Math.max(1, threads);

  const save = useMutation({
    mutationFn: () =>
      api.updateSettings({
        replicas,
        worker_threads: threads,
        autoscaling: {
          enabled: autoOn,
          min_replicas: autoMin,
          max_replicas: autoMax,
          lag_threshold: lagTarget,
        },
      }),
    onSuccess: (res) => {
      setMessage((res.notes ?? []).join(" ") || "Saved.");
      onSaved();
    },
    onError: (err) => setMessage(err instanceof Error ? err.message : "Save failed"),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Users className="h-4 w-4" />
          Workers
        </CardTitle>
        <CardDescription>
          Replicas and threads per worker. Thread changes roll worker pods.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <label className="block space-y-1 text-sm">
          <span>Replicas</span>
          <input
            type="number"
            min={0}
            max={w.max_replicas ?? 10}
            className="h-9 w-full rounded-md border bg-background px-2"
            value={replicas}
            onChange={(e) => setReplicas(Number(e.target.value))}
            disabled={!w.k8s_available}
          />
        </label>
        <label className="block space-y-1 text-sm">
          <span>Threads per worker ({w.threads_min}–{w.threads_max})</span>
          <input
            type="number"
            min={w.threads_min}
            max={w.threads_max}
            className="h-9 w-full rounded-md border bg-background px-2"
            value={threads}
            onChange={(e) => setThreads(Number(e.target.value))}
          />
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={autoOn} onChange={(e) => setAutoOn(e.target.checked)} disabled={!w.k8s_available} />
          Enable two-wave queue autoscaling
        </label>
        <div className="grid grid-cols-2 gap-2">
          <NumberField label="Min" value={autoMin} onChange={setAutoMin} disabled={!w.k8s_available} />
          <NumberField label="Max" value={autoMax} onChange={setAutoMax} disabled={!w.k8s_available} />
        </div>
        <p className="text-xs text-muted-foreground">
          Scale up only when waiting jobs exceed 2 waves of current workers
          (1 wave = replicas × {threads} threads). Target {lagTarget} pending jobs per
          worker. At most +2 pods / 30s, −1 pod / 60s.
        </p>
        <div className="text-xs text-muted-foreground">
          Ready {w.ready ?? 0} / desired {w.desired ?? 0}
          {!w.k8s_available ? " · Kubernetes API unavailable for replica changes" : ""}
        </div>
        <SaveRow saving={save.isPending} message={message} onSave={() => save.mutate()} />
      </CardContent>
    </Card>
  );
}

function QueueCard({
  settings,
  onSaved,
}: {
  settings: EngineSettings;
  onSaved: () => void;
}) {
  const q = settings.queue;
  const [maxJobs, setMaxJobs] = useState(q.max_global_jobs);
  const [message, setMessage] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: () => api.updateSettings({ max_global_jobs: maxJobs }),
    onSuccess: (res) => {
      setMessage((res.notes ?? []).join(" ") || "Saved.");
      onSaved();
    },
    onError: (err) => setMessage(err instanceof Error ? err.message : "Save failed"),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Layers className="h-4 w-4" />
          Queue
        </CardTitle>
        <CardDescription>Global concurrency cap and stream identity.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="text-sm">
          Mode <span className="font-medium">{q.mode}</span>
          {q.redis_available ? " · Redis connected" : " · Redis unavailable"}
        </div>
        <label className="block space-y-1 text-sm">
          <span>Max global jobs ({q.min_global_jobs}–{q.max_global_jobs_cap})</span>
          <input
            type="number"
            min={q.min_global_jobs}
            max={q.max_global_jobs_cap}
            className="h-9 w-full rounded-md border bg-background px-2"
            value={maxJobs}
            onChange={(e) => setMaxJobs(Number(e.target.value))}
          />
        </label>
        <div className="text-xs text-muted-foreground font-mono">
          {q.stream_key} · {q.consumer_group}
        </div>
        <SaveRow saving={save.isPending} message={message} onSave={() => save.mutate()} />
      </CardContent>
    </Card>
  );
}

function SchedulerCard({
  settings,
  onSaved,
}: {
  settings: EngineSettings;
  onSaved: () => void;
}) {
  const s = settings.scheduler;
  const [interval, setIntervalSec] = useState(s.check_interval_sec);
  const [message, setMessage] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: () => api.updateSettings({ scheduler_interval_sec: interval }),
    onSuccess: (res) => {
      setMessage((res.notes ?? []).join(" ") || "Saved.");
      onSaved();
    },
    onError: (err) => setMessage(err instanceof Error ? err.message : "Save failed"),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Timer className="h-4 w-4" />
          Scheduler
        </CardTitle>
        <CardDescription>How often the in-process loop claims due batch schedules.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="text-sm">
          {s.running ? "Running" : "Stopped"} · {s.enabled_count} enabled of {s.schedule_count} schedules
        </div>
        <label className="block space-y-1 text-sm">
          <span>Check interval (seconds)</span>
          <input
            type="number"
            min={5}
            max={3600}
            className="h-9 w-full rounded-md border bg-background px-2"
            value={interval}
            onChange={(e) => setIntervalSec(Number(e.target.value))}
          />
        </label>
        <SaveRow saving={save.isPending} message={message} onSave={() => save.mutate()} />
      </CardContent>
    </Card>
  );
}

function NumberField({
  label,
  value,
  onChange,
  disabled,
}: {
  label: string;
  value: number;
  onChange: (n: number) => void;
  disabled?: boolean;
}) {
  return (
    <label className="text-xs text-muted-foreground">
      {label}
      <input
        type="number"
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
        className="mt-1 h-9 w-full rounded-md border bg-background px-2 text-sm text-foreground"
      />
    </label>
  );
}

function SaveRow({
  saving,
  message,
  onSave,
}: {
  saving: boolean;
  message: string | null;
  onSave: () => void;
}) {
  return (
    <div className="space-y-2">
      <Button size="sm" onClick={onSave} disabled={saving}>
        <Save className="h-4 w-4" />
        {saving ? "Saving…" : "Save"}
      </Button>
      {message ? <p className="text-xs text-muted-foreground">{message}</p> : null}
    </div>
  );
}
