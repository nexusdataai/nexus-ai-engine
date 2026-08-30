import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Minus, Plus, XCircle } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { EmptyState } from "@/components/EmptyState";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useWorkersSnapshot } from "@/hooks/useQueueSnapshot";
import { cn, formatApiError, truncateId } from "@/lib/utils";
import { api } from "@/services/api";

type ActionFeedback = {
  type: "pending" | "success" | "error";
  message: string;
};

function FeedbackBanner({ feedback }: { feedback: ActionFeedback | null }) {
  if (!feedback) return null;
  const isSuccess = feedback.type === "success";
  const isPending = feedback.type === "pending";
  return (
    <div
      className={cn(
        "flex items-start gap-2 rounded-md border px-3 py-2 text-sm",
        isSuccess && "border-emerald-500/40 bg-emerald-500/10 text-emerald-200",
        isPending && "border-amber-500/40 bg-amber-500/10 text-amber-100",
        !isSuccess && !isPending && "border-red-500/40 bg-red-500/10 text-red-200",
      )}
      role="status"
      aria-live="polite"
    >
      {isSuccess ? (
        <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />
      ) : isPending ? (
        <span className="h-4 w-4 shrink-0 mt-0.5 animate-spin rounded-full border-2 border-amber-300 border-t-transparent" />
      ) : (
        <XCircle className="h-4 w-4 shrink-0 mt-0.5" />
      )}
      <span>{feedback.message}</span>
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
  const [lagThreshold, setLagThreshold] = useState<number | null>(null);
  const [scaleFeedback, setScaleFeedback] = useState<ActionFeedback | null>(null);
  const [autoscaleFeedback, setAutoscaleFeedback] = useState<ActionFeedback | null>(null);

  const currentReplicas = replicas ?? snap?.replicas ?? 1;
  const autoscaling = snap?.autoscaling;
  const autoOn = autoEnabled ?? autoscaling?.enabled ?? false;
  const autoMin = minReplicas ?? autoscaling?.min_replicas ?? 1;
  const autoMax = maxReplicas ?? autoscaling?.max_replicas ?? 10;
  const autoLag = lagThreshold ?? autoscaling?.lag_threshold ?? 5;

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
      const dep = data.deployment;
      setScaleFeedback({
        type: "success",
        message: dep
          ? `Scaled to ${dep.desired} desired / ${dep.ready} ready (was ${requestedReplicas} requested).`
          : `Scale request accepted: ${data.replicas ?? requestedReplicas} replica(s).`,
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
      setLagThreshold(null);
      await refreshWorkers();
      const enabled = Boolean(data.enabled ?? autoOn);
      setAutoscaleFeedback({
        type: "success",
        message: enabled
          ? `Autoscaling enabled (min ${data.min_replicas ?? autoMin}, max ${data.max_replicas ?? autoMax}, lag ${data.lag_threshold ?? autoLag}).`
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

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Workers</h2>
        <p className="text-sm text-muted-foreground">
          Job worker pods, Redis consumers, and scaling controls.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Desired replicas</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">{summary.isLoading ? "…" : (snap?.deployment.desired ?? 0)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Ready</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">{summary.isLoading ? "…" : (snap?.deployment.ready ?? 0)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Active consumers</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">{summary.isLoading ? "…" : (snap?.consumers ?? 0)}</p>
            {(snap?.registered_consumers ?? 0) > (snap?.consumers ?? 0) && (
              <p className="text-xs text-muted-foreground mt-1">
                {snap?.registered_consumers} registered in Redis
                {(snap?.stale_consumers ?? 0) > 0 ? ` · ${snap?.stale_consumers} stale` : ""}
              </p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Active jobs</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">{summary.isLoading ? "…" : (snap?.active_jobs ?? 0)}</p>
          </CardContent>
        </Card>
      </div>

      {scaleFeedback ? <FeedbackBanner feedback={scaleFeedback} /> : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Manual scale</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {!k8sAvailable && (
              <p className="text-sm text-amber-400">
                Kubernetes API unavailable — scaling disabled outside the cluster.
              </p>
            )}
            <div className="flex items-center gap-3">
              <Button
                variant="outline"
                size="icon"
                disabled={!k8sAvailable || scaleMutation.isPending || currentReplicas <= 0}
                onClick={() => setReplicas(Math.max(0, currentReplicas - 1))}
              >
                <Minus className="h-4 w-4" />
              </Button>
              <input
                type="number"
                min={0}
                max={snap?.max_worker_replicas ?? 10}
                value={currentReplicas}
                onChange={(e) => setReplicas(Number(e.target.value))}
                className="w-20 rounded-md border border-border bg-background px-2 py-1 text-center"
                disabled={!k8sAvailable}
              />
              <Button
                variant="outline"
                size="icon"
                disabled={
                  !k8sAvailable ||
                  scaleMutation.isPending ||
                  currentReplicas >= (snap?.max_worker_replicas ?? 10)
                }
                onClick={() => setReplicas(currentReplicas + 1)}
              >
                <Plus className="h-4 w-4" />
              </Button>
              <Button
                disabled={!k8sAvailable || scaleMutation.isPending}
                onClick={() => scaleMutation.mutate(currentReplicas)}
              >
                {scaleMutation.isPending ? "Applying…" : "Apply"}
              </Button>
            </div>
            {summary.isFetching && scaleMutation.isSuccess ? (
              <p className="text-xs text-muted-foreground">Refreshing worker status…</p>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Autoscaling (KEDA)</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {!autoscaling?.keda_available && (
              <p className="text-sm text-muted-foreground">
                KEDA not detected — install KEDA to enable queue-lag autoscaling.
              </p>
            )}
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={autoOn}
                onChange={(e) => setAutoEnabled(e.target.checked)}
                disabled={!k8sAvailable}
              />
              Enable autoscaling on queue lag
            </label>
            <div className="grid grid-cols-3 gap-2">
              <label className="text-xs text-muted-foreground">
                Min
                <input
                  type="number"
                  min={0}
                  value={autoMin}
                  onChange={(e) => setMinReplicas(Number(e.target.value))}
                  className="mt-1 w-full rounded border border-border bg-background px-2 py-1"
                  disabled={!k8sAvailable}
                />
              </label>
              <label className="text-xs text-muted-foreground">
                Max
                <input
                  type="number"
                  min={1}
                  value={autoMax}
                  onChange={(e) => setMaxReplicas(Number(e.target.value))}
                  className="mt-1 w-full rounded border border-border bg-background px-2 py-1"
                  disabled={!k8sAvailable}
                />
              </label>
              <label className="text-xs text-muted-foreground">
                Lag threshold
                <input
                  type="number"
                  min={1}
                  value={autoLag}
                  onChange={(e) => setLagThreshold(Number(e.target.value))}
                  className="mt-1 w-full rounded border border-border bg-background px-2 py-1"
                  disabled={!k8sAvailable}
                />
              </label>
            </div>
            <Button
              variant="outline"
              disabled={!k8sAvailable || autoscaleMutation.isPending}
              onClick={() => autoscaleMutation.mutate()}
            >
              {autoscaleMutation.isPending ? "Saving…" : "Save autoscaling"}
            </Button>
            <FeedbackBanner feedback={autoscaleFeedback} />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between gap-2">
            <CardTitle className="text-base">Worker registry</CardTitle>
            <Link to="/queue" className="text-sm text-primary hover:underline">
              View queue
            </Link>
          </div>
        </CardHeader>
        <CardContent>
          {workers.isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : rows.length === 0 ? (
            <EmptyState
              title="No workers registered"
              description="Start job-worker pods in queue mode to see Redis consumers here."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-muted-foreground">
                    <th className="py-2 pr-4">Pod</th>
                    <th className="py-2 pr-4">Consumer</th>
                    <th className="py-2 pr-4">Status</th>
                    <th className="py-2 pr-4">Current job</th>
                    <th className="py-2 pr-4">Pending</th>
                    <th className="py-2 pr-4">Restarts</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((w) => (
                    <tr key={w.worker_id} className="border-b border-border/60">
                      <td className="py-2 pr-4 font-mono">{truncateId(w.worker_id, 24)}</td>
                      <td className="py-2 pr-4 text-xs text-muted-foreground truncate max-w-[160px]">
                        {w.consumer_name ?? "—"}
                      </td>
                      <td className="py-2 pr-4">
                        <StatusBadge
                          status={
                            w.status === "healthy" || w.status === "idle"
                              ? "SUCCEEDED"
                              : w.status === "stale"
                                ? "PAUSED"
                                : w.status === "offline"
                                  ? "PENDING"
                                  : "FAILED"
                          }
                        />
                      </td>
                      <td className="py-2 pr-4">
                        {w.current_job ? (
                          <Link
                            to={`/executions/stage/${w.current_job.journey_id}/${w.current_job.job_id}`}
                            className="font-mono text-primary hover:underline"
                          >
                            {truncateId(w.current_job.job_id, 12)}
                          </Link>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="py-2 pr-4">{w.pending_jobs}</td>
                      <td className="py-2 pr-4">{w.restarts ?? 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
