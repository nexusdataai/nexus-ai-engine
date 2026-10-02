import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "@/App";

beforeEach(() => {
  document.documentElement.classList.add("dark");
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/api/v1/settings")) {
        return new Response(
          JSON.stringify({
            workers: {},
            queue: {},
            scheduler: {},
            version: { name: "nexus-ai-engine", version: "0.3.0" },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.includes("/version")) {
        return new Response(JSON.stringify({ version: "0.3.0" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url.includes("/api/v1/executions")) {
        return new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url.includes("/api/v1/journeys/")) {
        return new Response(JSON.stringify({ success: true, total: 0, data: [] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url.includes("/api/v1/fleet")) {
        return new Response(
          JSON.stringify({
            active: 0,
            queued: 0,
            failed: 0,
            workers: 0,
            global_limit: 10,
            generated_at: new Date().toISOString(),
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      return new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
});

describe("App", () => {
  it("renders dashboard with Journey Studio shell", async () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <App />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(screen.getByRole("heading", { level: 2, name: "Dashboard" })).toBeInTheDocument();
    expect(screen.getByTestId("active-execution-count")).toBeInTheDocument();
    expect(await screen.findByText("v0.3.0")).toBeInTheDocument();
  });
});
