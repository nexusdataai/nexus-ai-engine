import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { Icon } from "@/components/ds/Icon";
import { EmptyState, KeyValues, MetricStrip, Notice, Panel, SkeletonRows } from "@/components/ds/kit";
import { Button } from "@/components/ui/button";
import { api } from "@/services/api";

import { ConnectionPill, FLUSH_STRIP, RefreshButton, SectionHeader } from "./parts";

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
  const sseKeys = data?.sse?.keys || [];

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Redis Cache"
        description="Manage monitoring snapshots and SSE replay history. Job streams, waiting sets, and locks are not flushed here."
        meta={
          <>
            <ConnectionPill loading={isLoading} connected={data?.connected} />
            {data?.ping_ms != null && <span className="num text-sm text-muted-foreground">{data.ping_ms} ms</span>}
          </>
        }
        actions={
          <RefreshButton
            spinning={isFetching}
            disabled={isLoading || !!busy}
            onClick={() => qc.invalidateQueries({ queryKey: ["redis-cache"] })}
          >
            Refresh Status
          </RefreshButton>
        }
      />

      {message ? (
        <Notice tone="neutral" role="status" aria-live="polite">
          {message}
        </Notice>
      ) : null}

      <Panel
        title="Job queue"
        flush
        footer="Live stream state. This family is protected and cannot be flushed from here."
      >
        <MetricStrip
          columns={5}
          className={FLUSH_STRIP}
          items={[
            { label: "Stream", value: queue?.stream_length ?? 0 },
            { label: "Waiting", value: queue?.waiting ?? 0 },
            { label: "Active jobs", value: queue?.active ?? 0 },
            { label: "Pending", value: queue?.pending ?? 0 },
            { label: "Consumers", value: queue?.consumers ?? 0 },
          ]}
        />
      </Panel>

      <Panel title="Connection">
        <KeyValues
          columns={2}
          items={[
            { label: "Host", value: cfg?.redis_host || "—", mono: true },
            {
              label: "Memory",
              value: `${memory?.used_memory_human || "—"}${memory?.maxmemory_human && memory.maxmemory_human !== "0" ? ` / ${memory.maxmemory_human}` : ""}`,
            },
            { label: "Job stream", value: cfg?.job_stream_key || "—", mono: true },
            { label: "Queue mode / group", value: `${cfg?.queue_mode ? "on" : "off"} / ${cfg?.consumer_group || "—"}` },
          ]}
        />
      </Panel>

      <div className="grid gap-6 xl:grid-cols-2">
        <Panel
          title="Monitoring snapshots"
          flush
          actions={
            <>
              <Button
                size="sm"
                disabled={!!busy}
                onClick={() =>
                  void runAction("collect", () => api.collectRedisSnapshots(), "Snapshots collected")
                }
              >
                <Icon name="refresh" className={busy === "collect" ? "animate-spin" : undefined} />
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
                <Icon name="trash" />
                Flush snapshots
              </Button>
            </>
          }
          footer={<>{data?.snapshots?.key_total ?? 0} list entries across SLA, queue, and resource trend keys.</>}
        >
          {isLoading ? (
            <SkeletonRows rows={3} />
          ) : snapshots.length === 0 ? (
            <EmptyState bare icon="database" title="No snapshot keys" />
          ) : (
            <div className="scroll-thin overflow-x-auto">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Key</th>
                    <th className="r">Entries</th>
                  </tr>
                </thead>
                <tbody>
                  {snapshots.map((item) => (
                    <tr key={item.id}>
                      <td className="break-all font-mono text-xs text-foreground">{item.key}</td>
                      <td className="r num whitespace-nowrap text-foreground">{item.length}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>

        <Panel
          title="SSE history"
          flush
          actions={
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
              <Icon name="trash" />
              Flush SSE history
            </Button>
          }
          footer={
            <>
              {data?.sse?.key_total ?? 0} {data?.sse?.match || "sse:*:history"} keys. Replay buffers only — live pub/sub is not deleted.
            </>
          }
        >
          {isLoading ? (
            <SkeletonRows rows={3} />
          ) : sseKeys.length > 0 ? (
            <ul className="scroll-thin max-h-56 divide-y divide-border overflow-auto">
              {sseKeys.map((key) => (
                <li key={key} className="break-all px-4 py-2.5 font-mono text-xs text-foreground sm:px-5">
                  {key}
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState bare icon="history" title="No replay buffers" />
          )}
        </Panel>
      </div>
    </div>
  );
}
