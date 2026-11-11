import { useState } from "react";

import { Icon } from "@/components/ds/Icon";
import { CodeBlock, Panel, StatusPill } from "@/components/ds/kit";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { api, apiFetch } from "@/services/api";
import type { WorkersSummary } from "@/types/api";

import { SectionHeader } from "./parts";

const REST_PATHS = [
  "/health",
  "/readiness",
  "/api/v1/workers/summary",
  "/api/v1/journeys",
  "/api/v1/stages/registered",
  "/api/v1/monitoring/slas",
];

function RunIcon({ busy }: { busy: boolean }) {
  return <Icon name={busy ? "refresh" : "play"} className={busy ? "animate-spin" : undefined} />;
}

function Hint({ children }: { children: string }) {
  return <p className="mb-3 text-sm text-muted-foreground">{children}</p>;
}

export function AppDiagnosticsSection() {
  const [healthOut, setHealthOut] = useState("Waiting for connection test...");
  const [connected, setConnected] = useState<"unknown" | "connected" | "error">("unknown");
  const [apiPath, setApiPath] = useState("/health");
  const [apiMethod, setApiMethod] = useState<"GET" | "POST">("GET");
  const [apiBody, setApiBody] = useState("");
  const [apiOut, setApiOut] = useState("API response will appear here...");
  const [workerOut, setWorkerOut] = useState("Job worker pool statistics will appear here...");
  const [stagesOut, setStagesOut] = useState("Registered stages will appear here...");
  const [busy, setBusy] = useState<string | null>(null);

  const testConnection = async () => {
    setBusy("health");
    try {
      const [health, ready] = await Promise.all([
        apiFetch<{ status?: string; version?: string }>("/health"),
        apiFetch<{ ready?: boolean; version?: string }>("/readiness").catch((err) => ({ error: String(err) })),
      ]);
      setConnected("connected");
      setHealthOut(JSON.stringify({ health, readiness: ready }, null, 2));
    } catch (error) {
      setConnected("error");
      setHealthOut(`Connection failed: ${(error as Error).message}`);
    } finally {
      setBusy(null);
    }
  };

  const executeApi = async () => {
    setBusy("api");
    try {
      const body = apiMethod === "POST" && apiBody.trim() ? JSON.parse(apiBody) : undefined;
      const data = await apiFetch<unknown>(apiPath, { method: apiMethod, body });
      setApiOut(JSON.stringify(data, null, 2));
    } catch (error) {
      setApiOut(`API failed: ${(error as Error).message}`);
    } finally {
      setBusy(null);
    }
  };

  const loadWorkers = async () => {
    setBusy("workers");
    try {
      const data = await api.workersSummary();
      setWorkerOut(formatWorkers(data));
    } catch (error) {
      setWorkerOut(`Worker summary failed: ${(error as Error).message}`);
    } finally {
      setBusy(null);
    }
  };

  const loadStages = async () => {
    setBusy("stages");
    try {
      const data = await apiFetch<{ count?: number; stages?: Array<{ id?: string; name?: string }> }>("/api/v1/stages/registered");
      const lines = (data.stages || []).map((s) => `- ${s.id || s.name}`);
      setStagesOut(`Registered stages (${data.count ?? lines.length})\n\n${lines.join("\n") || "(none)"}`);
    } catch (error) {
      setStagesOut(`Stages list failed: ${(error as Error).message}`);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Backend Debug Platform"
        description="Test this ai-engine API, registered stages, and job workers. Call-processing MCP/QA tools are not part of this engine."
        meta={
          <StatusPill
            variant="soft"
            tone={connected === "connected" ? "success" : connected === "error" ? "danger" : "neutral"}
          >
            {connected === "connected" ? "Connected" : connected === "error" ? "Disconnected" : "Not tested"}
          </StatusPill>
        }
      />

      <div className="grid gap-6 xl:grid-cols-2">
        <Panel
          title="Connection Testing"
          actions={
            <Button size="sm" onClick={testConnection} disabled={busy === "health"}>
              <RunIcon busy={busy === "health"} />
              Test Connection
            </Button>
          }
        >
          <Hint>Hits /health and /readiness on this backend.</Hint>
          <CodeBlock wrap maxHeight={200}>{healthOut}</CodeBlock>
        </Panel>

        <Panel
          title="Registered stages"
          actions={
            <Button size="sm" variant="outline" onClick={loadStages} disabled={busy === "stages"}>
              <RunIcon busy={busy === "stages"} />
              List Stages
            </Button>
          }
        >
          <Hint>Stage classes this engine can execute.</Hint>
          <CodeBlock wrap maxHeight={200}>{stagesOut}</CodeBlock>
        </Panel>

        <Panel
          title="REST API Testing"
          actions={
            <Button size="sm" variant="outline" onClick={executeApi} disabled={busy === "api"}>
              <RunIcon busy={busy === "api"} />
              Execute API
            </Button>
          }
        >
          <Hint>Execute a request against this engine. /api/* uses the current session.</Hint>
          <div className="space-y-3">
            <div className="flex gap-2">
              <select
                className="field field-sm w-24 shrink-0"
                value={apiMethod}
                onChange={(e) => setApiMethod(e.target.value as "GET" | "POST")}
              >
                <option value="GET">GET</option>
                <option value="POST">POST</option>
              </select>
              <input className="field field-sm min-w-0 flex-1 font-mono" value={apiPath} onChange={(e) => setApiPath(e.target.value)} />
            </div>
            <div className="flex flex-wrap gap-1.5">
              {REST_PATHS.map((path) => (
                <button
                  key={path}
                  type="button"
                  className={cn(
                    "rounded-md border px-2 py-1 font-mono text-xs transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    apiPath === path
                      ? "border-border-strong bg-accent text-foreground"
                      : "border-border text-muted-foreground hover:bg-accent/70 hover:text-foreground",
                  )}
                  onClick={() => setApiPath(path)}
                >
                  {path}
                </button>
              ))}
            </div>
            {apiMethod === "POST" ? (
              <textarea
                className="field min-h-[72px] font-mono text-xs"
                value={apiBody}
                onChange={(e) => setApiBody(e.target.value)}
                placeholder="{}"
              />
            ) : null}
            <CodeBlock wrap maxHeight={200}>{apiOut}</CodeBlock>
          </div>
        </Panel>

        <Panel
          title="Job worker pool"
          actions={
            <Button size="sm" variant="outline" onClick={loadWorkers} disabled={busy === "workers"}>
              <RunIcon busy={busy === "workers"} />
              Get Worker Stats
            </Button>
          }
        >
          <Hint>Queue consumers and deployment replicas for this engine.</Hint>
          <CodeBlock wrap maxHeight={200}>{workerOut}</CodeBlock>
        </Panel>
      </div>
    </div>
  );
}

function formatWorkers(data: WorkersSummary): string {
  const dep = data.deployment;
  return [
    "Job Engine Worker Pool",
    "",
    `Queue mode: ${data.queue_mode}`,
    `Replicas desired/ready: ${dep?.desired ?? "—"}/${dep?.ready ?? "—"}`,
    `Consumers: ${data.consumers} healthy, ${data.stale_consumers ?? 0} stale`,
    `Active jobs: ${data.active_jobs}`,
    `Autoscaling: ${data.autoscaling?.enabled ? "on" : "off"} (${data.autoscaling?.min_replicas}-${data.autoscaling?.max_replicas})`,
  ].join("\n");
}
