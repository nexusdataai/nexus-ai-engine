import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { QueuePage } from "@/pages/QueuePage";

import { installMockEventSource } from "./mockEventSource";

describe("QueuePage", () => {
  beforeEach(() => {
    installMockEventSource();
    let summaryHits = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo) => {
        const url = String(input);
        if (url.includes("/api/v1/queue/summary")) {
          summaryHits += 1;
          return new Response(
            JSON.stringify({
              lag: 0,
              pending: 0,
              active: summaryHits,
              queued: 0,
              max_global: 50,
              consumer_count: 1,
              worker_threads: 1,
              running_capacity: 3,
              generated_at: new Date().toISOString(),
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        if (url.includes("/api/v1/queue/jobs")) {
          return new Response(JSON.stringify({ jobs: [], count: 0, state: "all" }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response("{}", { status: 404 });
      }),
    );
  });

  it("refresh button refetches queue summary", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <QueuePage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await waitFor(() => expect(screen.getByTestId("queue-running-count")).toHaveTextContent("1"));

    fireEvent.click(screen.getByTestId("queue-refresh"));

    await waitFor(() => expect(screen.getByTestId("queue-running-count")).toHaveTextContent("2"));
  });
});
