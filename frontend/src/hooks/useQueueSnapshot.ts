import { useQuery } from "@tanstack/react-query";

import { api } from "@/services/api";

export function useQueueSnapshot() {
  const summary = useQuery({
    queryKey: ["queue", "summary"],
    queryFn: () => api.queueSummary(),
    refetchInterval: 1_000,
    retry: 1,
  });

  const jobs = useQuery({
    queryKey: ["queue", "jobs"],
    queryFn: () => api.queueJobs("all", 50),
    refetchInterval: 1_000,
    retry: 1,
  });

  return { summary, jobs };
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
