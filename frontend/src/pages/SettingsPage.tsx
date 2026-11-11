import { useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Icon, type IconName } from "@/components/ds/Icon";
import { Field, InlineError, KeyValues, PageHeader, SkeletonRows, StatusPill, TableShell } from "@/components/ds/kit";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { api } from "@/services/api";
import type { EngineSettings } from "@/types/api";

type SectionId = "workers" | "queue" | "scheduler" | "about";

const SECTIONS: { id: SectionId; label: string; icon: IconName; hint: string }[] = [
  { id: "workers", label: "Workers", icon: "server", hint: "Replicas, threads, autoscaling" },
  { id: "queue", label: "Queue", icon: "layers", hint: "Concurrency cap, stream" },
  { id: "scheduler", label: "Scheduler", icon: "clock", hint: "Batch schedule loop" },
  { id: "about", label: "About", icon: "info", hint: "Version and environment" },
];

export function SettingsPage() {
  const qc = useQueryClient();
  const [section, setSection] = useState<SectionId>("workers");
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["settings"],
    queryFn: () => api.getSettings(),
  });
  const onSaved = () => qc.invalidateQueries({ queryKey: ["settings"] });

  return (
    <div className="space-y-5">
      <PageHeader title="Settings" description="Worker, queue, and scheduler settings for this ai-engine." />

      {isLoading ? (
        <TableShell>
          <SkeletonRows rows={6} />
        </TableShell>
      ) : error || !data ? (
        <InlineError onRetry={() => refetch()}>{error ? String(error) : "Could not load settings"}</InlineError>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[232px_minmax(0,1fr)]">
          <nav aria-label="Settings sections" className="scrollbar-hide -mx-1 flex gap-1 overflow-x-auto px-1 lg:mx-0 lg:flex-col lg:overflow-visible lg:px-0">
            {SECTIONS.map((s) => {
              const on = s.id === section;
              return (
                <button
                  key={s.id}
                  type="button"
                  aria-current={on ? "page" : undefined}
                  onClick={() => setSection(s.id)}
                  className={cn(
                    "group flex shrink-0 items-center gap-2.5 rounded-md px-2.5 py-2 text-left text-sm transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    on ? "bg-accent font-medium text-foreground" : "text-muted-foreground hover:bg-accent/70 hover:text-foreground",
                  )}
                >
                  <Icon name={s.icon} className={cn("h-[17px] w-[17px]", on ? "text-primary dark:text-brand-hi" : "text-subtle-foreground")} />
                  <span className="min-w-0">
                    <span className="block truncate">{s.label}</span>
                    <span className="hidden truncate text-xs font-normal text-subtle-foreground lg:block">{s.hint}</span>
                  </span>
                </button>
              );
            })}
          </nav>

          <div className="min-w-0 max-w-[760px]">
            {section === "workers" ? <WorkersCard settings={data} onSaved={onSaved} /> : null}
            {section === "queue" ? <QueueCard settings={data} onSaved={onSaved} /> : null}
            {section === "scheduler" ? <SchedulerCard settings={data} onSaved={onSaved} /> : null}
            {section === "about" ? <AboutCard settings={data} /> : null}
          </div>
        </div>
      )}
    </div>
  );
}

/** One settings section: heading, live state line, form, save row. */
function Section({
  title,
  description,
  state,
  children,
  footer,
}: {
  title: string;
  description: string;
  state?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <section className="overflow-hidden rounded-xl border border-border bg-card shadow-xs">
      <header className="border-b border-border px-5 py-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="text-lg font-medium text-foreground">{title}</h3>
          {state}
        </div>
        <p className="mt-0.5 text-sm text-muted-foreground">{description}</p>
      </header>
      <div className="space-y-5 px-5 py-5">{children}</div>
      {footer ? <footer className="border-t border-border bg-surface-2/40 px-5 py-3">{footer}</footer> : null}
    </section>
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

  const ready = w.ready ?? 0;
  const desired = w.desired ?? 0;

  return (
    <Section
      title="Workers"
      description="Replicas and threads per worker. Thread changes roll worker pods."
      state={
        <StatusPill tone={desired > 0 && ready >= desired ? "success" : "warning"} variant="soft">
          Ready {ready} / desired {desired}
        </StatusPill>
      }
      footer={<SaveRow saving={save.isPending} message={message} onSave={() => save.mutate()} />}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field
          label="Replicas"
          htmlFor="set-replicas"
          hint={!w.k8s_available ? "Kubernetes API unavailable for replica changes" : `Up to ${w.max_replicas ?? 10}`}
        >
          <input
            id="set-replicas"
            type="number"
            min={0}
            max={w.max_replicas ?? 10}
            className="field num"
            value={replicas}
            onChange={(e) => setReplicas(Number(e.target.value))}
            disabled={!w.k8s_available}
          />
        </Field>
        <Field label={`Threads per worker (${w.threads_min}–${w.threads_max})`} htmlFor="set-threads" hint="Jobs one pod runs at the same time">
          <input
            id="set-threads"
            type="number"
            min={w.threads_min}
            max={w.threads_max}
            className="field num"
            value={threads}
            onChange={(e) => setThreads(Number(e.target.value))}
          />
        </Field>
      </div>

      <div className="border-t border-border pt-5">
        <label className="flex cursor-pointer items-center gap-2.5 text-sm font-medium text-foreground">
          <input type="checkbox" className="check" checked={autoOn} onChange={(e) => setAutoOn(e.target.checked)} disabled={!w.k8s_available} />
          Enable two-wave queue autoscaling
        </label>
        <div className="mt-3 grid grid-cols-2 gap-4">
          <NumberField label="Min" value={autoMin} onChange={setAutoMin} disabled={!w.k8s_available} />
          <NumberField label="Max" value={autoMax} onChange={setAutoMax} disabled={!w.k8s_available} />
        </div>
        <p className="mt-3 text-xs leading-5 text-muted-foreground">
          Scale up only when waiting jobs exceed 2 waves of current workers
          (1 wave = replicas × {threads} threads). Target {lagTarget} pending jobs per
          worker. At most +2 pods / 30s, −1 pod / 60s.
        </p>
      </div>
    </Section>
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
    <Section
      title="Queue"
      description="Global concurrency cap and stream identity."
      state={
        <StatusPill tone={q.redis_available ? "success" : "danger"} variant="soft">
          {q.redis_available ? "Redis connected" : "Redis unavailable"}
        </StatusPill>
      }
      footer={<SaveRow saving={save.isPending} message={message} onSave={() => save.mutate()} />}
    >
      <Field
        label={`Max global jobs (${q.min_global_jobs}–${q.max_global_jobs_cap})`}
        htmlFor="set-maxjobs"
        hint="The most jobs the whole engine runs at once, across all workers"
        className="max-w-xs"
      >
        <input
          id="set-maxjobs"
          type="number"
          min={q.min_global_jobs}
          max={q.max_global_jobs_cap}
          className="field num"
          value={maxJobs}
          onChange={(e) => setMaxJobs(Number(e.target.value))}
        />
      </Field>
      <KeyValues
        items={[
          { label: "Mode", value: q.mode },
          { label: "Stream key", value: q.stream_key, mono: true },
          { label: "Consumer group", value: q.consumer_group, mono: true },
        ]}
      />
    </Section>
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
    <Section
      title="Scheduler"
      description="How often the in-process loop claims due batch schedules."
      state={
        <StatusPill tone={s.running ? "success" : "danger"} variant="soft" live={s.running}>
          {s.running ? "Running" : "Stopped"}
        </StatusPill>
      }
      footer={<SaveRow saving={save.isPending} message={message} onSave={() => save.mutate()} />}
    >
      <p className="text-sm text-muted-foreground">
        <span className="num font-medium text-foreground">{s.enabled_count}</span> enabled of{" "}
        <span className="num font-medium text-foreground">{s.schedule_count}</span> schedules
      </p>
      <Field label="Check interval (seconds)" htmlFor="set-interval" hint="Between 5 and 3600 seconds" className="max-w-xs">
        <input
          id="set-interval"
          type="number"
          min={5}
          max={3600}
          className="field num"
          value={interval}
          onChange={(e) => setIntervalSec(Number(e.target.value))}
        />
      </Field>
    </Section>
  );
}

function AboutCard({ settings }: { settings: EngineSettings }) {
  const v = settings.version;
  return (
    <Section title="About" description="The engine build this console is connected to.">
      <KeyValues
        items={[
          { label: "Product", value: v.name },
          { label: "Version", value: v.version, mono: true },
          { label: "Environment", value: v.env },
          ...(v.git_sha && v.git_sha !== "unknown" ? [{ label: "Git", value: v.git_sha, mono: true }] : []),
        ]}
      />
    </Section>
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
    <label className="block text-xs font-medium text-muted-foreground">
      {label}
      <input
        type="number"
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
        className="field num mt-1.5 font-normal"
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
    <div className="flex flex-wrap items-center justify-between gap-3">
      <p className="min-w-0 text-xs text-muted-foreground" role="status">{message ?? "Changes apply to the running engine."}</p>
      <Button size="sm" onClick={onSave} disabled={saving}>
        <Icon name={saving ? "spinner" : "check"} className={saving ? "animate-spin" : undefined} />
        {saving ? "Saving…" : "Save"}
      </Button>
    </div>
  );
}
