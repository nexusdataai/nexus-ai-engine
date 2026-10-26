import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/services/api";
import type { QueueJobsResponse, QueueSummary } from "@/types/api";

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";
const POLL_MS = 2_000;
const SSE_STALE_MS = 8_000;

export function useQueueSnapshot() {
  const queryClient = useQueryClient();
  const [live, setLive] = useState(false);
  const lastSseAt = useRef(0);

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

  useEffect(() => {
    const es = new EventSource(`${API_BASE}/api/v1/queue/stream`);
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
        }
        if (data.jobs) {
          queryClient.setQueryData(["queue", "jobs"], {
            jobs: data.jobs,
            count: data.count ?? data.jobs.length,
            state: data.state ?? "all",
          });
        }
        lastSseAt.current = Date.now();
        setLive(true);
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
  }, [queryClient]);

  const refresh = async () => {
    await Promise.all([summary.refetch(), jobs.refetch()]);
  };

  return { summary, jobs, live, refresh };
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
