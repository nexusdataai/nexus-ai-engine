import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/services/api";
import type { QueueJobsResponse, QueueSummary } from "@/types/api";

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";

export function useQueueSnapshot() {
  const queryClient = useQueryClient();
  const [live, setLive] = useState(false);

  const summary = useQuery({
    queryKey: ["queue", "summary"],
    queryFn: () => api.queueSummary(),
    refetchInterval: live ? 15_000 : 2_000,
    retry: 1,
  });

  const jobs = useQuery({
    queryKey: ["queue", "jobs"],
    queryFn: () => api.queueJobs("all", 200),
    refetchInterval: live ? 15_000 : 2_000,
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
        setLive(true);
      } catch {
        /* ignore malformed frames */
      }
    };
    es.addEventListener("queue", onQueue);
    es.onerror = () => setLive(false);
    return () => {
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
