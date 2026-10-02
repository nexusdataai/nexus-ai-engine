import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Database, RefreshCw, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/services/api";

export function RedisCacheSection() {
  const qc = useQueryClient();
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["redis-cache"],
    queryFn: () => api.getRedisOverview(),
    refetchInterval: 30_000,
  });

  const runAction = async (name: string, action: () => Promise<{ keys_deleted?: number; collected?: boolean; error?: string }>, success: string) => {
    setBusy(name);
    setMessage(null);
    try {
      const result = await action();
      if (result.error) {
        setMessage(result.error);
      } else {
        setMessage(success.replace("{n}", String(result.keys_deleted ?? 0)));
      }
      await qc.invalidateQueries({ queryKey: ["redis-cache"] });
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  };

  const cfg = data?.effective_config;
  const memory = data?.memory;
  const queue = data?.queue;
  const snapshots = data?.snapshots?.keys ?? [];

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Database className="h-5 w-5" />
            Redis Cache
          </CardTitle>
          <CardDescription>
            Manage monitoring snapshots and SSE replay history. Job streams, waiting sets, and locks are not flushed here.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              onClick={() => qc.invalidateQueries({ queryKey: ["redis-cache"] })}
              disabled={isLoading || !!busy}
            >
              <RefreshCw className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`} />
              Refresh Status
            </Button>
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                data?.connected ? "bg-emerald-600/20 text-emerald-400" : "bg-red-600/20 text-red-400"
              }`}
            >
              {isLoading ? "checking" : data?.connected ? "connected" : "disconnected"}
            </span>
            {data?.ping_ms != null && <span className="text-sm text-muted-foreground">{data.ping_ms} ms</span>}
          </div>
          {message ? <p className="text-sm text-muted-foreground">{message}</p> : null}

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 text-sm">
            <div className="border rounded-lg p-3">
              <div className="text-muted-foreground">Host</div>
              <div className="font-medium">{cfg?.redis_host || "—"}</div>
            </div>
            <div className="border rounded-lg p-3">
              <div className="text-muted-foreground">Memory</div>
              <div className="font-medium">
                {memory?.used_memory_human || "—"}
                {memory?.maxmemory_human && memory.maxmemory_human !== "0" ? ` / ${memory.maxmemory_human}` : ""}
              </div>
            </div>
            <div className="border rounded-lg p-3">
              <div className="text-muted-foreground">Job stream</div>
              <div className="font-medium">{cfg?.job_stream_key || "—"}</div>
            </div>
            <div className="border rounded-lg p-3">
              <div className="text-muted-foreground">Queue mode / group</div>
              <div className="font-medium">
                {cfg?.queue_mode ? "on" : "off"} / {cfg?.consumer_group || "—"}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Monitoring snapshots</CardTitle>
          <CardDescription>
            {data?.snapshots?.key_total ?? 0} list entries across SLA, queue, and resource trend keys.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="text-sm border rounded-lg divide-y">
            {snapshots.map((item) => (
              <div key={item.id} className="flex justify-between gap-3 px-3 py-2">
                <span className="font-mono break-all">{item.key}</span>
                <span className="text-muted-foreground shrink-0">{item.length} entries</span>
              </div>
            ))}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              disabled={!!busy}
              onClick={() =>
                void runAction("collect", () => api.collectRedisSnapshots(), "Snapshots collected")
              }
            >
              <RefreshCw className={`h-4 w-4 ${busy === "collect" ? "animate-spin" : ""}`} />
              Collect now
            </Button>
            <Button
              size="sm"
              variant="destructive"
              disabled={!!busy}
              onClick={() => {
                if (!window.confirm("Flush SLA, queue, and resource snapshot lists? Job streams and SSE keys are not deleted.")) {
                  return;
                }
                void runAction(
                  "flush-snap",
                  () => api.flushRedisSnapshots(),
                  "Flushed {n} snapshot key(s)",
                );
              }}
            >
              <Trash2 className="h-4 w-4" />
              Flush snapshots
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Job queue</CardTitle>
          <CardDescription>
            Live stream state. This family is protected and cannot be flushed from here.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3 text-sm">
            <div className="border rounded-lg p-3">
              <div className="text-muted-foreground">Stream</div>
              <div className="font-medium">{queue?.stream_length ?? 0}</div>
            </div>
            <div className="border rounded-lg p-3">
              <div className="text-muted-foreground">Waiting</div>
              <div className="font-medium">{queue?.waiting ?? 0}</div>
            </div>
            <div className="border rounded-lg p-3">
              <div className="text-muted-foreground">Active jobs</div>
              <div className="font-medium">{queue?.active ?? 0}</div>
            </div>
            <div className="border rounded-lg p-3">
              <div className="text-muted-foreground">Pending</div>
              <div className="font-medium">{queue?.pending ?? 0}</div>
            </div>
            <div className="border rounded-lg p-3">
              <div className="text-muted-foreground">Consumers</div>
              <div className="font-medium">{queue?.consumers ?? 0}</div>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">SSE history</CardTitle>
          <CardDescription>
            {data?.sse?.key_total ?? 0} {data?.sse?.match || "sse:*:history"} keys. Replay buffers only — live pub/sub is not deleted.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {(data?.sse?.keys || []).length > 0 ? (
            <div className="text-sm border rounded-lg divide-y max-h-48 overflow-auto">
              {(data?.sse?.keys || []).map((key) => (
                <div key={key} className="px-3 py-2 font-mono break-all">
                  {key}
                </div>
              ))}
            </div>
          ) : null}
          <Button
            size="sm"
            variant="destructive"
            disabled={!!busy}
            onClick={() => {
              if (!window.confirm("Flush sse:*:history keys? Job streams and monitoring snapshots are not deleted.")) {
                return;
              }
              void runAction("flush-sse", () => api.flushRedisSseHistory(), "Flushed {n} SSE history key(s)");
            }}
          >
            <Trash2 className="h-4 w-4" />
            Flush SSE history
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
