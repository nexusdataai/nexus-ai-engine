import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { Icon } from "@/components/ds/Icon";
import { EmptyState, Field, MetricStrip, Notice, PageHeader, Panel, SkeletonRows, StatusPill, SubHeading, type Tone } from "@/components/ds/kit";
import { Button } from "@/components/ui/button";
import { shortWorkerName } from "@/components/workers/WorkerHealthList";
import { useWorkersSnapshot } from "@/hooks/useQueueSnapshot";
import { cn, formatApiError, truncateId } from "@/lib/utils";
import { relativeTime } from "@/utils/time";
import { api } from "@/services/api";

type ActionFeedback = {
  type: "pending" | "success" | "error";
  message: string;
};

function FeedbackBanner({ feedback }: { feedback: ActionFeedback | null }) {
  if (!feedback) return null;
  const tone: Tone = feedback.type === "success" ? "success" : feedback.type === "pending" ? "warning" : "danger";
  return (
    <Notice tone={tone} role="status" aria-live="polite">
      {feedback.message}
    </Notice>
  );
}

const WORKER_STATUS: Record<string, { label: string; tone: Tone }> = {
  healthy: { label: "Healthy", tone: "success" },
  idle: { label: "Idle", tone: "neutral" },
  stale: { label: "Stale", tone: "warning" },
  offline: { label: "Offline", tone: "danger" },
};

/**
 * One cell per possible replica: ready pods are filled, pods still starting
 * are outlined, the rest is headroom up to the cluster maximum. The bracket
 * underneath marks the autoscaling range.
 */
function ReplicaRail({ ready, desired, max, autoMin, autoMax, autoOn }: { ready: number; desired: number; max: number; autoMin: number; autoMax: number; autoOn: boolean }) {
  const cells = Math.max(max, desired, 1);
  return (
    <div>
      <div className="flex gap-1.5" role="img" aria-label={`${ready} of ${desired} replicas ready, maximum ${max}`}>
        {Array.from({ length: cells }).map((_, i) => (
          <span
            key={i}
            className={cn(
              "h-8 min-w-0 flex-1 rounded-md border transition-colors duration-slow",
              i < ready
                ? "border-brand/50 bg-brand/25"
                : i < desired
                  ? "border-warning/50 bg-warning/10"
                  : "border-dashed border-border-strong/70",
            )}
          />
        ))}
      </div>
      {autoOn && (
        <div className="mt-1.5 flex gap-1.5" aria-hidden="true">
          {Array.from({ length: cells }).map((_, i) => (
            <span key={i} className={cn("h-0.5 flex-1 rounded-full", i >= Math.max(autoMin - 1, 0) && i < autoMax ? "bg-border-strong" : "bg-transparent")} />
          ))}
        </div>
      )}
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-[2px] bg-brand/60" /> Ready</span>
        <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-[2px] border border-warning/60 bg-warning/20" /> Starting</span>
        <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-[2px] border border-dashed border-border-strong" /> Headroom</span>
        {autoOn && <span>Autoscaling range {autoMin}–{autoMax}</span>}
      </div>
    </div>
  );
}

export function WorkersPage() {
  const queryClient = useQueryClient();
  const { summary, workers } = useWorkersSnapshot();
  const snap = summary.data;
  const rows = workers.data?.workers ?? [];

  const [replicas, setReplicas] = useState<number | null>(null);
  const [autoEnabled, setAutoEnabled] = useState<boolean | null>(null);
  const [minReplicas, setMinReplicas] = useState<number | null>(null);
  const [maxReplicas, setMaxReplicas] = useState<number | null>(null);
  const [scaleFeedback, setScaleFeedback] = useState<ActionFeedback | null>(null);
  const [autoscaleFeedback, setAutoscaleFeedback] = useState<ActionFeedback | null>(null);

  const currentReplicas = replicas ?? snap?.replicas ?? 1;
  const autoscaling = snap?.autoscaling;
  const autoOn = autoEnabled ?? autoscaling?.enabled ?? false;
  const autoMin = minReplicas ?? autoscaling?.min_replicas ?? 1;
  const autoMax = maxReplicas ?? autoscaling?.max_replicas ?? 10;
  const autoThreads = autoscaling?.threads ?? 3;
  const autoLag = autoscaling?.lag_threshold ?? 2 * autoThreads;

  const refreshWorkers = async () => {
    await Promise.all([
      queryClient.refetchQueries({ queryKey: ["workers", "summary"] }),
      queryClient.refetchQueries({ queryKey: ["workers", "list"] }),
    ]);
  };

  const scaleMutation = useMutation({
    mutationFn: (n: number) => api.scaleWorkers(n),
    onMutate: (requestedReplicas) => {
      setScaleFeedback({
        type: "pending",
        message: `Scaling to ${requestedReplicas} replica(s)…`,
      });
    },
    onSuccess: async (data, requestedReplicas) => {
      setReplicas(null);
      await refreshWorkers();
      const dep = data.deployment as { desired?: number; ready?: number } | undefined;
      const kedaSynced = Boolean(data.keda_synced);
      const base = dep
        ? `Scaled to ${dep.desired} desired / ${dep.ready} ready.`
        : `Scale request accepted: ${data.replicas ?? requestedReplicas} replica(s).`;
      setScaleFeedback({
        type: "success",
        message: kedaSynced
          ? `${base} KEDA min replicas updated to match (autoscaling still active).`
          : base,
      });
    },
    onError: (error) => {
      setScaleFeedback({
        type: "error",
        message: formatApiError(error),
      });
    },
  });

  const autoscaleMutation = useMutation({
    mutationFn: () =>
      api.configureWorkerAutoscaling({
        enabled: autoOn,
        min_replicas: autoMin,
        max_replicas: autoMax,
        lag_threshold: autoLag,
      }),
    onMutate: () => setAutoscaleFeedback(null),
    onSuccess: async (data) => {
      setAutoEnabled(null);
      setMinReplicas(null);
      setMaxReplicas(null);
      await refreshWorkers();
      const enabled = Boolean(data.enabled ?? autoOn);
      setAutoscaleFeedback({
        type: "success",
        message: enabled
          ? `Two-wave autoscaling enabled (min ${data.min_replicas ?? autoMin}, max ${data.max_replicas ?? autoMax}, ${data.lag_threshold ?? autoLag} pending/worker).`
          : "Autoscaling disabled — manual replica count applies. Check the box above to enable KEDA scaling.",
      });
    },
    onError: (error) => {
      setAutoscaleFeedback({
        type: "error",
        message: formatApiError(error),
      });
    },
  });

  const k8sAvailable = snap?.k8s_available ?? false;
  const desired = snap?.deployment.desired ?? 0;
  const ready = snap?.deployment.ready ?? 0;
  const maxWorkers = snap?.max_worker_replicas ?? 10;
  const scaleDirty = replicas != null && replicas !== snap?.replicas;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Workers"
        description="Job worker pods, Redis consumers, and scaling controls."
        meta={
          summary.isLoading ? null : (
            <StatusPill tone={desired > 0 && ready >= desired ? "success" : ready > 0 ? "warning" : "danger"} variant="soft">
              {ready} of {desired} ready
            </StatusPill>
          )
        }
        actions={
          <Button variant="outline" size="sm" asChild>
            <Link to="/queue">
              <Icon name="layers" />
              View queue
            </Link>
          </Button>
        }
      />

      <MetricStrip
        items={[
          { label: "Desired replicas", value: summary.isLoading ? "…" : desired, hint: `Up to ${maxWorkers} allowed` },
          { label: "Ready", value: summary.isLoading ? "…" : ready, tone: !summary.isLoading && ready < desired ? "warning" : undefined, hint: snap?.deployment.name },
          {
            label: "Active consumers",
            value: summary.isLoading ? "…" : (snap?.consumers ?? 0),
            hint:
              (snap?.registered_consumers ?? 0) > (snap?.consumers ?? 0)
                ? `${snap?.registered_consumers} registered in Redis${(snap?.stale_consumers ?? 0) > 0 ? ` · ${snap?.stale_consumers} stale` : ""}`
                : `${snap?.healthy_consumers ?? 0} healthy`,
          },
          { label: "Active jobs", value: summary.isLoading ? "…" : (snap?.active_jobs ?? 0), hint: "Running on this pool" },
        ]}
      />

      {scaleFeedback ? <FeedbackBanner feedback={scaleFeedback} /> : null}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="min-w-0 space-y-6">
          <Panel title="Worker pool" description="Replicas against the cluster maximum.">
            {summary.isLoading ? (
              <SkeletonRows rows={2} className="p-0" />
            ) : (
              <ReplicaRail ready={ready} desired={desired} max={maxWorkers} autoMin={autoscaling?.min_replicas ?? 1} autoMax={autoscaling?.max_replicas ?? maxWorkers} autoOn={Boolean(autoscaling?.enabled)} />
            )}
          </Panel>

          <Panel title="Worker registry" description={rows.length > 0 ? `${rows.length} pods` : undefined} flush>
            {workers.isLoading ? (
              <SkeletonRows rows={3} />
            ) : rows.length === 0 ? (
              <EmptyState
                bare
                icon="server"
                title="No workers registered"
                description="Start job-worker pods in queue mode to see Redis consumers here."
              />
            ) : (
              <div className="scroll-thin overflow-x-auto">
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>Pod</th>
                      <th>Status</th>
                      <th>Current job</th>
                      <th className="r">Pending</th>
                      <th className="r">Restarts</th>
                      <th>Started</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((w) => {
                      const st = WORKER_STATUS[w.status] ?? { label: w.status || "Unknown", tone: "danger" as Tone };
                      return (
                        <tr key={w.worker_id}>
                          <td className="max-w-[280px]">
                            <span className="block truncate font-mono text-sm text-foreground" title={w.worker_id}>
                              {shortWorkerName(w.worker_id)}
                            </span>
                            <span className="block truncate text-xs text-muted-foreground" title={w.consumer_name ?? undefined}>
                              {w.phase ? `${w.phase} · ` : ""}seen {relativeTime(w.last_seen)}
                            </span>
                          </td>
                          <td>
                            <StatusPill tone={st.tone} live={Boolean(w.current_job)}>{st.label}</StatusPill>
                          </td>
                          <td>
                            {w.current_job ? (
                              <Link
                                to={`/executions/stage/${w.current_job.journey_id}/${w.current_job.job_id}`}
                                className="link font-mono text-xs"
                              >
                                {truncateId(w.current_job.job_id, 12)}
                              </Link>
                            ) : (
                              <span className="text-subtle-foreground">Idle</span>
                            )}
                          </td>
                          <td className="r num">{w.pending_jobs}</td>
                          <td className={cn("r num", (w.restarts ?? 0) > 0 && "text-warning")}>{w.restarts ?? 0}</td>
                          <td className="whitespace-nowrap text-muted-foreground">{w.start_time ? relativeTime(w.start_time) : "—"}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </div>

        <Panel title="Scaling" bodyClassName="space-y-6">
          {!k8sAvailable && !summary.isLoading && (
            <Notice tone="warning">Kubernetes API unavailable — scaling disabled outside the cluster.</Notice>
          )}

          <div>
            <SubHeading>Manual scale</SubHeading>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="icon"
                aria-label="One replica fewer"
                disabled={!k8sAvailable || scaleMutation.isPending || currentReplicas <= 0}
                onClick={() => setReplicas(Math.max(0, currentReplicas - 1))}
              >
                <Icon name="minus" />
              </Button>
              <input
                type="number"
                aria-label="Replicas"
                min={0}
                max={maxWorkers}
                value={currentReplicas}
                onChange={(e) => setReplicas(Number(e.target.value))}
                className="field num w-20 text-center"
                disabled={!k8sAvailable}
              />
              <Button
                variant="outline"
                size="icon"
                aria-label="One replica more"
                disabled={!k8sAvailable || scaleMutation.isPending || currentReplicas >= maxWorkers}
                onClick={() => setReplicas(currentReplicas + 1)}
              >
                <Icon name="plus" />
              </Button>
              <Button
                className="ml-auto"
                variant={scaleDirty ? "default" : "outline"}
                disabled={!k8sAvailable || scaleMutation.isPending}
                onClick={() => scaleMutation.mutate(currentReplicas)}
              >
                {scaleMutation.isPending ? "Applying…" : "Apply"}
              </Button>
            </div>
            {summary.isFetching && scaleMutation.isSuccess ? (
              <p className="mt-2 text-xs text-muted-foreground">Refreshing worker status…</p>
            ) : null}
          </div>

          <div className="border-t border-border pt-5">
            <SubHeading>Autoscaling (KEDA)</SubHeading>
            {!autoscaling?.keda_available && !summary.isLoading && (
              <p className="mb-3 text-sm text-muted-foreground">
                KEDA not detected — install KEDA to enable queue-lag autoscaling.
              </p>
            )}
            <label className="flex cursor-pointer items-center gap-2.5 text-sm text-foreground">
              <input
                type="checkbox"
                className="check"
                checked={autoOn}
                onChange={(e) => setAutoEnabled(e.target.checked)}
                disabled={!k8sAvailable}
              />
              Enable two-wave queue autoscaling
            </label>
            <div className="mt-3 grid grid-cols-2 gap-3">
              <Field label="Min" htmlFor="auto-min">
                <input
                  id="auto-min"
                  type="number"
                  min={0}
                  value={autoMin}
                  onChange={(e) => setMinReplicas(Number(e.target.value))}
                  className="field num"
                  disabled={!k8sAvailable}
                />
              </Field>
              <Field label="Max" htmlFor="auto-max">
                <input
                  id="auto-max"
                  type="number"
                  min={1}
                  value={autoMax}
                  onChange={(e) => setMaxReplicas(Number(e.target.value))}
                  className="field num"
                  disabled={!k8sAvailable}
                />
              </Field>
            </div>
            <p className="mt-3 text-xs leading-5 text-muted-foreground">
              Scale up only when waiting jobs exceed 2 waves of current workers
              (1 wave = replicas × {autoThreads} threads). Target {autoLag} pending jobs
              per worker. At most +2 pods / 30s, −1 pod / 60s.
            </p>
            <Button
              className="mt-3"
              variant="outline"
              disabled={!k8sAvailable || autoscaleMutation.isPending}
              onClick={() => autoscaleMutation.mutate()}
            >
              {autoscaleMutation.isPending ? "Saving…" : "Save autoscaling"}
            </Button>
            {autoscaleFeedback ? <div className="mt-3"><FeedbackBanner feedback={autoscaleFeedback} /></div> : null}
          </div>
        </Panel>
      </div>
    </div>
  );
}
