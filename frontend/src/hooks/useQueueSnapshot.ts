import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { sseBaseUrl } from "@/utils/sseBaseUrl";
import { api } from "@/services/api";
import type { QueueJobsResponse, QueueSummary } from "@/types/api";

const POLL_MS = 2_000;
const SSE_STALE_MS = 8_000;
const JOBS_INVALIDATE_THROTTLE_MS = 2_000;

export function useQueueSnapshot() {
  const queryClient = useQueryClient();
  const [live, setLive] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const lastSseAt = useRef(0);
  const lastJobsInvalidateAt = useRef(0);

  const summary = useQuery({
    queryKey: ["queue", "summary"],
    queryFn: () => api.queueSummary(),
    refetchInterval: POLL_MS,
    retry: 1,
  });

  const jobs = useQuery({
    queryKey: ["queue", "jobs"],
    queryFn: () => api.queueJobs("all", 200),
    refetchInterval: POLL_MS,
    retry: 1,
  });

  const maybeRefreshJobs = useCallback(() => {
    const now = Date.now();
    if (now - lastJobsInvalidateAt.current < JOBS_INVALIDATE_THROTTLE_MS) return;
    lastJobsInvalidateAt.current = now;
    void queryClient.invalidateQueries({ queryKey: ["queue", "jobs"] });
  }, [queryClient]);

  useEffect(() => {
    const base = sseBaseUrl();
    if (!base) return;

    const es = new EventSource(`${base}/api/v1/queue/stream`);
    const markLive = () => {
      lastSseAt.current = Date.now();
      setLive(true);
    };

    es.onopen = () => markLive();

    const onQueue = (ev: MessageEvent) => {
      try {
        const data = JSON.parse(ev.data) as {
          summary?: QueueSummary;
          jobs?: QueueJobsResponse["jobs"];
          count?: number;
          state?: string;
        };
        if (data.summary) {
          queryClient.setQueryData(["queue", "summary"], data.summary);
          maybeRefreshJobs();
        }
        if (data.jobs) {
          queryClient.setQueryData(["queue", "jobs"], {
            jobs: data.jobs,
            count: data.count ?? data.jobs.length,
            state: data.state ?? "all",
          });
        }
        markLive();
      } catch {
        /* ignore malformed frames */
      }
    };
    es.addEventListener("queue", onQueue);
    es.onerror = () => setLive(false);
    const staleTimer = window.setInterval(() => {
      if (lastSseAt.current && Date.now() - lastSseAt.current > SSE_STALE_MS) {
        setLive(false);
      }
    }, POLL_MS);
    return () => {
      window.clearInterval(staleTimer);
      es.removeEventListener("queue", onQueue);
      es.close();
      setLive(false);
    };
  }, [queryClient, maybeRefreshJobs]);

  const refresh = useCallback(async () => {
    setIsRefreshing(true);
    try {
      await Promise.all([
        queryClient.fetchQuery({
          queryKey: ["queue", "summary"],
          queryFn: () => api.queueSummary(),
          staleTime: 0,
        }),
        queryClient.fetchQuery({
          queryKey: ["queue", "jobs"],
          queryFn: () => api.queueJobs("all", 200),
          staleTime: 0,
        }),
      ]);
    } finally {
      setIsRefreshing(false);
    }
  }, [queryClient]);

  const busy = isRefreshing || summary.isFetching || jobs.isFetching;

  return { summary, jobs, live, refresh, isRefreshing: busy };
}

export function useWorkersSnapshot() {
  const summary = useQuery({
    queryKey: ["workers", "summary"],
    queryFn: () => api.workersSummary(),
    refetchInterval: 5_000,
    retry: 1,
  });

  const workers = useQuery({
    queryKey: ["workers", "list"],
    queryFn: () => api.listQueueWorkers(),
    refetchInterval: 2_000,
    retry: 1,
  });

  return { summary, workers };
}
