/**
 * SSE wiring checks for live-update pages.
 *
 * | Page / surface              | Hook                 | Stream URL |
 * |-----------------------------|----------------------|------------|
 * | Queue                       | useQueueSnapshot     | /api/v1/queue/stream |
 * | Stage job / journey detail  | useJourneyJobStream  | /api/v1/journeys/:id/jobs/:job/stream |
 * | DSL execution detail        | useExecutionStream   | /api/v1/executions/:id/stream |
 * | Workers, Dashboard          | (polling only)       | — |
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor, act } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useExecutionStream } from "@/hooks/useExecutionStream";
import { useJourneyJobStream } from "@/hooks/useJourneyJobStream";
import { useQueueSnapshot } from "@/hooks/useQueueSnapshot";

import { MockEventSource, installMockEventSource } from "./mockEventSource";

const queueSummary = {
  lag: 0,
  pending: 0,
  active: 1,
  queued: 0,
  max_global: 50,
  consumer_count: 1,
  worker_threads: 1,
  running_capacity: 3,
  generated_at: new Date().toISOString(),
};

const queueJobs = {
  jobs: [
    {
      stream_id: "1-0",
      job_id: "JOB-1",
      journey_id: "JRN-1",
      job_kind: "transformation",
      state: "running",
      consumer_name: "w1",
      idle_ms: 0,
    },
  ],
  count: 1,
  state: "all",
};

function wrapper(client: QueryClient) {
  return function W({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

describe("SSE hooks", () => {
  beforeEach(() => {
    installMockEventSource();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo) => {
        const url = String(input);
        if (url.includes("/api/v1/queue/summary")) {
          return new Response(JSON.stringify(queueSummary), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (url.includes("/api/v1/queue/jobs")) {
          return new Response(JSON.stringify(queueJobs), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response("{}", { status: 404 });
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    MockEventSource.reset();
  });

  it("useQueueSnapshot opens queue stream and marks live on SSE", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => useQueueSnapshot(), { wrapper: wrapper(client) });

    await waitFor(() => expect(result.current.summary.data?.active).toBe(1));

    const es = MockEventSource.instances.find((i) => i.url.includes("/api/v1/queue/stream"));
    expect(es).toBeTruthy();
    act(() => {
      es!.emit("queue", { summary: { ...queueSummary, active: 2 } });
    });
    await waitFor(() => expect(result.current.live).toBe(true));
    await waitFor(() => expect(result.current.summary.data?.active).toBe(2));
  });

  it("useQueueSnapshot refresh forces new fetches", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const fetchMock = global.fetch as ReturnType<typeof vi.fn>;
    const { result } = renderHook(() => useQueueSnapshot(), { wrapper: wrapper(client) });

    await waitFor(() => expect(result.current.summary.isSuccess).toBe(true));
    const before = fetchMock.mock.calls.length;

    await act(async () => {
      await result.current.refresh();
    });

    expect(fetchMock.mock.calls.length).toBeGreaterThan(before);
    expect(result.current.isRefreshing).toBe(false);
  });

  it("useJourneyJobStream keeps one EventSource across parent re-renders", async () => {
    const stages = [
      {
        id: "stg1",
        name: "S",
        order: 1,
        steps: [{ id: "step1", name: "Step", order: 1 }],
      },
    ];
    const client = new QueryClient();
    const onComplete = vi.fn();
    const { result, rerender } = renderHook(
      ({ status }: { status: string }) =>
        useJourneyJobStream("JRN-1", stages, "JOB-1", status, onComplete),
      { wrapper: wrapper(client), initialProps: { status: "running" } },
    );

    await waitFor(() => expect(MockEventSource.instances.length).toBeGreaterThan(0));
    const countAfterMount = MockEventSource.instances.length;

    rerender({ status: "running" });
    rerender({ status: "running" });

    expect(MockEventSource.instances.length).toBe(countAfterMount);
    expect(result.current.sseStatus).toBe("connected");
  });

  it("useExecutionStream connects to execution stream", async () => {
    const { result } = renderHook(() => useExecutionStream("exec-1"));

    await waitFor(() => expect(result.current.connected).toBe(true));
    const es = MockEventSource.instances.find((i) => i.url.includes("/api/v1/executions/exec-1/stream"));
    expect(es).toBeTruthy();
  });
});
