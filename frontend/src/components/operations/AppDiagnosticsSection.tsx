import { useState } from "react";
import { Play, RefreshCw, Server, Wrench } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api, apiFetch } from "@/services/api";
import type { WorkersSummary } from "@/types/api";

const REST_PATHS = [
  "/health",
  "/readiness",
  "/api/v1/workers/summary",
  "/api/v1/journeys",
  "/api/v1/stages/registered",
  "/api/v1/monitoring/slas",
];

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
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold">Backend Debug Platform</h3>
        <p className="text-sm text-muted-foreground">
          Test this ai-engine API, registered stages, and job workers. Call-processing MCP/QA tools are not part of this engine.
        </p>
        <div className="mt-2 flex items-center gap-2 text-sm">
          <span className={`h-2 w-2 rounded-full ${connected === "connected" ? "bg-green-500" : connected === "error" ? "bg-red-500" : "bg-muted-foreground"}`} />
          {connected === "connected" ? "Connected" : connected === "error" ? "Disconnected" : "Not tested"}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Server className="h-4 w-4" />
              Connection Testing
            </CardTitle>
            <CardDescription>Hits /health and /readiness on this backend.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Button size="sm" onClick={testConnection} disabled={busy === "health"}>
              {busy === "health" ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              Test Connection
            </Button>
            <pre className="p-3 bg-muted rounded-lg text-xs overflow-auto max-h-40 font-mono whitespace-pre-wrap">{healthOut}</pre>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Wrench className="h-4 w-4" />
              Registered stages
            </CardTitle>
            <CardDescription>Stage classes this engine can execute.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Button size="sm" onClick={loadStages} disabled={busy === "stages"}>
              {busy === "stages" ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              List Stages
            </Button>
            <pre className="p-3 bg-muted rounded-lg text-xs overflow-auto max-h-40 font-mono whitespace-pre-wrap">{stagesOut}</pre>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">REST API Testing</CardTitle>
            <CardDescription>Execute a request against this engine. /api/* uses the current session.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex flex-wrap gap-1">
              {REST_PATHS.map((path) => (
                <button
                  key={path}
                  type="button"
                  className="text-xs rounded border px-2 py-1 text-muted-foreground hover:text-foreground"
                  onClick={() => setApiPath(path)}
                >
                  {path}
                </button>
              ))}
            </div>
            <div className="flex gap-2">
              <select className="h-8 rounded-md border bg-background px-2 text-xs" value={apiMethod} onChange={(e) => setApiMethod(e.target.value as "GET" | "POST")}>
                <option value="GET">GET</option>
                <option value="POST">POST</option>
              </select>
              <input className="h-8 flex-1 rounded-md border bg-background px-2 text-xs" value={apiPath} onChange={(e) => setApiPath(e.target.value)} />
            </div>
            {apiMethod === "POST" ? (
              <textarea className="w-full min-h-[72px] rounded-md border bg-background p-2 text-xs font-mono" value={apiBody} onChange={(e) => setApiBody(e.target.value)} placeholder="{}" />
            ) : null}
            <Button size="sm" onClick={executeApi} disabled={busy === "api"}>
              {busy === "api" ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              Execute API
            </Button>
            <pre className="p-3 bg-muted rounded-lg text-xs overflow-auto max-h-40 font-mono whitespace-pre-wrap">{apiOut}</pre>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Job worker pool</CardTitle>
            <CardDescription>Queue consumers and deployment replicas for this engine.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Button size="sm" onClick={loadWorkers} disabled={busy === "workers"}>
              {busy === "workers" ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              Get Worker Stats
            </Button>
            <pre className="p-3 bg-muted rounded-lg text-xs overflow-auto max-h-40 font-mono whitespace-pre-wrap">{workerOut}</pre>
          </CardContent>
        </Card>
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
