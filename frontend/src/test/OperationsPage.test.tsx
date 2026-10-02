import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { OperationsPage } from "@/pages/OperationsPage";
import type { SlaSummaryResponse } from "@/types/monitoring";

const SLA_FIXTURE: SlaSummaryResponse = {
  window: "1h",
  window_hours: 1,
  overall_score: 92.4,
  overall_status: "warning",
  pillars: {
    performance: {
      score: 94.0,
      status: "warning",
      summary_metrics: [{ label: "API p95", value: "120ms" }],
    },
    availability: { score: 99.0, status: "healthy", summary_metrics: [{ label: "Uptime", value: "100.0%" }] },
    reliability: { score: 97.0, status: "healthy", summary_metrics: [{ label: "Success Rate", value: "100.0%" }] },
    security: { score: 90.0, status: "warning", summary_metrics: [{ label: "Auth Method", value: "Local" }] },
    compliance: { score: 82.0, status: "warning", summary_metrics: [{ label: "RBAC", value: "Not configured" }] },
  },
};

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/api/v1/monitoring/slas/timeline")) {
        return new Response(JSON.stringify({ hours: 24, points: [] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url.includes("/api/v1/monitoring/slas/")) {
        return new Response(JSON.stringify({ pillar: "performance", score: 94, status: "warning" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url.includes("/api/v1/monitoring/dynamodb")) {
        return new Response(
          JSON.stringify({
            connected: true,
            ping_ms: 12,
            region: "us-east-1",
            table_total: 4,
            tables_active: 3,
            tables: [
              {
                id: "journeys",
                label: "Journeys",
                name: "ai-engine-local-journeys",
                status: "ACTIVE",
                item_count: 10,
                size_human: "1.20MB",
                gsi_count: 1,
              },
            ],
            kpis: [
              { id: "read_rcu", label: "Read capacity", value: 1.2, unit: "RCU" },
              { id: "write_wcu", label: "Write capacity", value: 0.4, unit: "WCU" },
              { id: "read_latency", label: "Read latency", value: 8, unit: "ms" },
              { id: "write_latency", label: "Write latency", value: 12, unit: "ms" },
            ],
            points: [
              {
                timestamp: "2026-09-06T12:00:00Z",
                read_rcu: 1.2,
                write_wcu: 0.4,
                read_latency_ms: 8,
                write_latency_ms: 12,
              },
            ],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.includes("/api/v1/diagnostics/infrastructure")) {
        return new Response(
          JSON.stringify({
            status: "healthy",
            timestamp: "2026-09-06T12:00:00Z",
            checks: {
              frontend_serving: { status: "pass", latency_ms: 12, message: "Frontend serving HTML" },
              dynamodb_tables: { status: "pass", latency_ms: 40, message: "All 4 engine tables: read+write OK" },
            },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.includes("/api/v1/dlq")) {
        return new Response(
          JSON.stringify({
            table: "ai-engine-local-dlq",
            count: 1,
            summary: { pending_review: 0, reprocessed: 1, dismissed: 0 },
            items: [
              {
                pk: "dlq",
                sk: "2026-09-06T19:38:10.843207Z#JOB-004",
                job_id: "JOB-004",
                journey_id: "JRN-1",
                stage_id: "fulfillment_handoff",
                error: "Seeded for DLQ UI verification",
                status: "reprocessed",
                new_job_id: "JOB-106",
              },
            ],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.includes("/api/v1/runbooks/stale-jobs")) {
        return new Response(
          JSON.stringify({ summary: { total_stale: 0, STALE: 0, "LIKELY-STUCK": 0, "UNVERIFIED-LONG": 0, blocked_schedules: 0 }, jobs: [] }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.includes("/api/v1/runbooks/crashes")) {
        return new Response(
          JSON.stringify({ namespace: "ai-engine-local", available: true, pods: [], count: 0 }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.includes("/api/v1/monitoring/athena")) {
        return new Response(
          JSON.stringify({
            connected: true,
            glue_reachable: true,
            athena_reachable: true,
            ping_ms: 18,
            region: "us-east-1",
            database: "default",
            workgroup: "primary",
            table: { name: "archived_jobs", exists: true, partition_count: 4, record_count: 20 },
            recent_queries: [{ id: "q-1", state: "SUCCEEDED", engine_ms: 120, kind: "read" }],
            kpis: [
              { id: "read_queries", label: "Read queries", value: 3, unit: "count" },
              { id: "write_queries", label: "Write queries", value: 1, unit: "count" },
              { id: "bytes_scanned", label: "Data scanned", value: 4096, unit: "bytes" },
              { id: "avg_engine_ms", label: "Avg engine time", value: 120, unit: "ms" },
            ],
            points: [{ timestamp: "2026-09-06T12:00:00Z", read_queries: 3, write_queries: 1, bytes_scanned: 4096, avg_engine_ms: 120 }],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.includes("/api/v1/monitoring/redis")) {
        return new Response(
          JSON.stringify({
            connected: true,
            ping_ms: 0.77,
            memory: { used_memory_human: "4.50M", maxmemory_human: "256.00M" },
            effective_config: {
              redis_host: "redis:6379",
              job_stream_key: "ai-engine:jobs",
              consumer_group: "ai-engine-workers",
              queue_mode: true,
            },
            snapshots: {
              key_total: 3,
              keys: [{ id: "sla", key: "ai-engine:sla-snapshots", label: "SLA snapshots", length: 3 }],
            },
            queue: { stream_length: 5, waiting: 1, active: 0, pending: 0, consumers: 2, protected: true },
            sse: { key_total: 0, keys: [], match: "sse:*:history" },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.includes("/api/v1/monitoring/resources")) {
        return new Response(
          JSON.stringify({
            window: "1h",
            grain: "minute",
            node: "k3s-node",
            kpis: [
              { id: "cpu", label: "CPU", value: 12.5, unit: "%" },
              { id: "memory", label: "Memory", value: 29.0, unit: "%" },
              { id: "storage", label: "Storage", value: 41.0, unit: "%" },
              { id: "network", label: "Network", value: 0.42, unit: "Mbps" },
              { id: "jobs", label: "Jobs running", value: 3, unit: "count" },
            ],
            points: [
              {
                timestamp: new Date().toISOString(),
                cpu_pct: 12.5,
                memory_pct: 29.0,
                storage_pct: 41.0,
                network_rx_mbps: 0.3,
                network_tx_mbps: 0.12,
                jobs_running: 3,
              },
            ],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.includes("/api/v1/monitoring/app/")) {
        return new Response(
          JSON.stringify({
            tab: "executions",
            window: "24h",
            grain: "hour",
            chart_title: "Execution volume and success rate",
            kpis: [
              { id: "active", label: "Active now", value: 2, unit: "count" },
              { id: "submitted", label: "Submitted", value: 10, unit: "count" },
              { id: "succeeded", label: "Succeeded", value: 8, unit: "count" },
              { id: "failed", label: "Failed", value: 2, unit: "count" },
              { id: "success_rate", label: "Success rate", value: 80, unit: "%" },
              { id: "p95", label: "Dispatch p95", value: 120, unit: "ms" },
            ],
            series: [
              { id: "succeeded", label: "Succeeded", color: "#22c55e", axis: "count" },
              { id: "failed", label: "Failed", color: "#ef4444", axis: "count" },
              { id: "rate", label: "Success rate", color: "#eab308", axis: "percent" },
            ],
            mix: [
              { id: "succeeded", label: "Succeeded", value: 8, color: "#22c55e" },
              { id: "failed", label: "Failed", value: 2, color: "#ef4444" },
            ],
            points: [
              { timestamp: new Date().toISOString(), succeeded: 3, failed: 1, rate: 75 },
            ],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.includes("/api/v1/monitoring/slas")) {
        return new Response(JSON.stringify(SLA_FIXTURE), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url.includes("/api/v1/settings")) {
        return new Response(
          JSON.stringify({ version: { name: "nexus-ai-engine", version: "0.3.0" } }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      return new Response(JSON.stringify({}), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
});

function renderOperations(path = "/operations") {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/operations" element={<OperationsPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("OperationsPage", () => {
  it("defaults to System SLAs and renders scores from fixture", async () => {
    renderOperations();
    expect(screen.getByRole("heading", { level: 2, name: "Operations" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /System SLAs/i })).toBeInTheDocument();
    expect(await screen.findByText("Performance")).toBeInTheDocument();
    expect(await screen.findByText("92.4%")).toBeInTheDocument();
    expect(screen.getByText("94")).toBeInTheDocument();
    expect(screen.getByText("Availability")).toBeInTheDocument();
    expect(screen.getByText("Reliability")).toBeInTheDocument();
    expect(screen.getByText("Security")).toBeInTheDocument();
    expect(screen.getByText("Compliance")).toBeInTheDocument();
  });

  it("renders execution trend KPIs on the App Executions tab", async () => {
    renderOperations("/operations?view=monitoring&section=app&tab=executions");
    expect(await screen.findByText("Executions trends")).toBeInTheDocument();
    expect(await screen.findByText("Success rate")).toBeInTheDocument();
    expect(screen.getByText("80.0%")).toBeInTheDocument();
    expect(screen.getByText("Submitted")).toBeInTheDocument();
    expect(screen.getAllByText("Execution volume and success rate").length).toBeGreaterThan(0);
  });

  it("renders Resource Monitoring KPIs on the Infra resources tab", async () => {
    renderOperations("/operations?view=monitoring&section=infra&tab=resources");
    expect(await screen.findByRole("heading", { name: "Resource Monitoring" })).toBeInTheDocument();
    expect(await screen.findByText("CPU")).toBeInTheDocument();
    expect(screen.getByText("12.5%")).toBeInTheDocument();
    expect(screen.getByText("Jobs running")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText(/k3s-node/)).toBeInTheDocument();
  });

  it("places Redis Cache after Resource Monitoring, then DynamoDB and Athena", () => {
    renderOperations();
    const tabs = screen.getAllByRole("button").map((el) => el.textContent);
    const slas = tabs.findIndex((t) => t?.includes("System SLAs"));
    const resources = tabs.findIndex((t) => t?.includes("Resource Monitoring"));
    const redis = tabs.findIndex((t) => t === "Redis Cache" || t?.includes("Redis Cache"));
    const dynamo = tabs.findIndex((t) => t?.includes("DynamoDB"));
    const athena = tabs.findIndex((t) => t?.includes("Athena Database"));
    expect(resources).toBe(slas + 1);
    expect(redis).toBe(resources + 1);
    expect(dynamo).toBe(redis + 1);
    expect(athena).toBe(dynamo + 1);
  });

  it("renders Redis Cache overview for ai-engine keys", async () => {
    renderOperations("/operations?view=monitoring&section=infra&tab=redis-cache");
    expect(await screen.findByRole("heading", { name: "Redis Cache" })).toBeInTheDocument();
    expect(await screen.findByText("connected")).toBeInTheDocument();
    expect(screen.getByText("redis:6379")).toBeInTheDocument();
    expect(screen.getByText("ai-engine:jobs")).toBeInTheDocument();
    expect(screen.getByText("Monitoring snapshots")).toBeInTheDocument();
    expect(screen.getByText("Job queue")).toBeInTheDocument();
    expect(screen.getByText("Flush snapshots")).toBeInTheDocument();
  });

  it("renders DynamoDB engine tables", async () => {
    renderOperations("/operations?view=monitoring&section=infra&tab=dynamodb");
    expect(await screen.findByRole("heading", { name: "DynamoDB" })).toBeInTheDocument();
    expect(await screen.findByText("connected")).toBeInTheDocument();
    expect(screen.getByText("ai-engine-local-journeys")).toBeInTheDocument();
    expect(screen.getByText("3 / 4 active")).toBeInTheDocument();
    expect(screen.getByText("Read capacity")).toBeInTheDocument();
    expect(screen.getByText("Write capacity")).toBeInTheDocument();
    expect(screen.getByText("Read / write capacity")).toBeInTheDocument();
    expect(screen.getByText("Read / write latency")).toBeInTheDocument();
  });

  it("renders Athena archive catalog status", async () => {
    renderOperations("/operations?view=monitoring&section=infra&tab=athena");
    expect(await screen.findByRole("heading", { name: "Athena Database" })).toBeInTheDocument();
    expect(await screen.findByText("connected")).toBeInTheDocument();
    expect(screen.getByText("default")).toBeInTheDocument();
    expect(screen.getByText("archived_jobs", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("Read queries")).toBeInTheDocument();
    expect(screen.getByText("Write queries")).toBeInTheDocument();
    expect(screen.getByText("Read / write query trend")).toBeInTheDocument();
  });

  it("renders Infra diagnostics categories", () => {
    renderOperations("/operations?view=diagnostics&tab=infrastructure");
    expect(screen.getByText("Infrastructure Diagnostics")).toBeInTheDocument();
    expect(screen.getByText("Frontend Health")).toBeInTheDocument();
    expect(screen.getByText("DynamoDB (Read+Write)")).toBeInTheDocument();
    expect(screen.getByText("Glue / Athena")).toBeInTheDocument();
    expect(screen.getByText("Redis Cache")).toBeInTheDocument();
    expect(screen.queryByText("Call DB Query")).not.toBeInTheDocument();
  });

  it("renders App diagnostics without call-processing tools", () => {
    renderOperations("/operations?view=diagnostics&tab=diagnostics");
    expect(screen.getByText("Backend Debug Platform")).toBeInTheDocument();
    expect(screen.getByText("REST API Testing")).toBeInTheDocument();
    expect(screen.getByText("Job worker pool")).toBeInTheDocument();
    expect(screen.queryByText(/MCP Tools/i)).not.toBeInTheDocument();
  });

  it("renders Stale Job Manager runbook", () => {
    renderOperations("/operations?view=runbooks&tab=stale-jobs");
    expect(screen.getByText("Scan Stale Jobs")).toBeInTheDocument();
    expect(screen.getByText("Cancel All Stale")).toBeInTheDocument();
    expect(screen.getByText("Run a scan to list stuck in-progress jobs.")).toBeInTheDocument();
    expect(screen.queryByText("Missing Recording Analyzer")).not.toBeInTheDocument();
  });

  it("renders Dead Letter Queue runbook", async () => {
    renderOperations("/operations?view=runbooks&tab=dlq");
    expect(screen.getByText("Load DLQ")).toBeInTheDocument();
    expect(screen.getByText("Import Failed Jobs")).toBeInTheDocument();
    expect(await screen.findByText("JOB-004")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /Select JOB-004/i })).not.toBeDisabled();
    expect(screen.getByText("Re-run")).toBeInTheDocument();
  });
});
