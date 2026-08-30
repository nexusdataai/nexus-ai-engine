import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { cn } from "@/lib/utils";
import type { LogEntry, StepStatus } from "@/types/stageJobStream";

function fmtTime(ts: string): string {
  try {
    return new Date(ts).toLocaleTimeString(undefined, { hour12: false });
  } catch {
    return ts;
  }
}

function normalizeLevel(level: string): string {
  return level.toLowerCase();
}

type Props = {
  stepId: string;
  stepName: string;
  status: StepStatus;
  logs: LogEntry[];
  levelFilter: string;
  onLevelFilterChange: (level: string) => void;
  variant?: "inline" | "panel";
};

export function StepConsole({
  stepName,
  status,
  logs,
  levelFilter,
  onLevelFilterChange,
  variant = "inline",
}: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [followTail, setFollowTail] = useState(true);

  const filtered = useMemo(() => {
    if (!levelFilter || levelFilter === "all") return logs;
    return logs.filter((l) => {
      const lv = normalizeLevel(l.level);
      if (levelFilter === "warn") return lv === "warn" || lv === "warning";
      if (levelFilter === "error") return lv === "error";
      if (levelFilter === "info") return lv === "info" || lv === "debug";
      return true;
    });
  }, [logs, levelFilter]);

  useEffect(() => {
    if (!followTail || !scrollRef.current) return;
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [filtered.length, followTail]);

  const onScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 12;
    setFollowTail(atBottom);
  }, []);

  return (
    <div
      className={cn(
        "rounded-md border border-border bg-zinc-950/80 overflow-hidden flex flex-col",
        variant === "inline" ? "mt-2" : "h-full min-h-[420px]",
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 border-b border-border/60 bg-zinc-900/50">
        <div className="flex items-center gap-2 text-xs">
          <span
            className={cn(
              "h-2 w-2 rounded-full",
              status === "running" && "bg-blue-400 animate-pulse",
              status === "completed" && "bg-emerald-400",
              status === "failed" && "bg-red-400",
              status === "pending" && "bg-muted-foreground",
            )}
          />
          <span className="font-medium">{stepName}</span>
          <span className="text-muted-foreground">{logs.length} lines</span>
        </div>
        <div className="flex gap-1">
          {(["all", "info", "warn", "error"] as const).map((lv) => (
            <button
              key={lv}
              type="button"
              className={cn(
                "px-2 py-0.5 rounded text-[10px] uppercase tracking-wide",
                levelFilter === lv ? "bg-primary/20 text-primary" : "text-muted-foreground hover:bg-accent",
              )}
              onClick={() => onLevelFilterChange(lv)}
            >
              {lv}
            </button>
          ))}
        </div>
      </div>
      <div
        ref={scrollRef}
        onScroll={onScroll}
        className={cn(
          "overflow-y-auto p-3 font-mono text-[11px] leading-relaxed flex-1",
          variant === "inline" ? "max-h-48" : "min-h-0",
        )}
        data-testid="step-console"
      >
        {filtered.length === 0 ? (
          <p className="text-muted-foreground">Waiting for output…</p>
        ) : (
          filtered.map((line, i) => (
            <div key={`${line.timestamp}-${i}`} className="whitespace-pre-wrap break-all">
              <span className="text-muted-foreground">{fmtTime(line.timestamp)}</span>{" "}
              <span
                className={cn(
                  normalizeLevel(line.level) === "error" && "text-red-400",
                  normalizeLevel(line.level) === "warn" && "text-amber-400",
                  normalizeLevel(line.level) === "info" && "text-blue-300",
                )}
              >
                [{line.level.toUpperCase()}]
              </span>{" "}
              {line.message}
            </div>
          ))
        )}
      </div>
      {!followTail && filtered.length > 0 ? (
        <button
          type="button"
          className="w-full py-1 text-xs text-primary hover:bg-accent border-t border-border/60"
          onClick={() => {
            if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
            setFollowTail(true);
          }}
        >
          ↓ Jump to latest
        </button>
      ) : null}
    </div>
  );
}
