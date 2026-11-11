import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Icon } from "@/components/ds/Icon";
import { Segmented, StatusPill } from "@/components/ds/kit";
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

const LEVELS = [
  { value: "all", label: "All" },
  { value: "info", label: "Info" },
  { value: "warn", label: "Warn" },
  { value: "error", label: "Error" },
] as const;

/** Log output of one step. Follows the tail until the reader scrolls up. */
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
        "relative flex flex-col overflow-hidden",
        variant === "inline" ? "mt-2 rounded-lg border border-border" : "h-full min-h-[420px]",
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-2">
        <div className="flex min-w-0 items-center gap-3 text-sm">
          <StatusPill status={status} />
          {variant === "inline" ? <span className="truncate font-medium text-foreground">{stepName}</span> : null}
          <span className="num shrink-0 text-xs text-muted-foreground">{logs.length} lines</span>
        </div>
        <Segmented
          label="Log level"
          value={(levelFilter || "all") as (typeof LEVELS)[number]["value"]}
          onChange={onLevelFilterChange}
          options={LEVELS.map((l) => ({ value: l.value, label: l.label }))}
        />
      </div>
      <div
        ref={scrollRef}
        onScroll={onScroll}
        className={cn(
          "scroll-thin flex-1 overflow-y-auto bg-background p-4 font-mono text-xs leading-5",
          variant === "inline" ? "max-h-48" : "min-h-0",
        )}
        data-testid="step-console"
      >
        {filtered.length === 0 ? (
          <p className="font-sans text-sm text-subtle-foreground">Waiting for output…</p>
        ) : (
          filtered.map((line, i) => {
            const lv = normalizeLevel(line.level);
            return (
              <div key={`${line.timestamp}-${i}`} className="flex gap-3 whitespace-pre-wrap break-all">
                <span className="num shrink-0 select-none text-subtle-foreground">{fmtTime(line.timestamp)}</span>
                <span
                  className={cn(
                    "w-[52px] shrink-0 select-none",
                    lv === "error" && "text-destructive",
                    (lv === "warn" || lv === "warning") && "text-warning",
                    lv === "info" && "text-primary dark:text-brand-hi",
                    lv === "debug" && "text-subtle-foreground",
                  )}
                >
                  {line.level.toUpperCase()}
                </span>
                <span className={cn("min-w-0 text-foreground", lv === "error" && "text-destructive")}>{line.message}</span>
              </div>
            );
          })
        )}
      </div>
      {!followTail && filtered.length > 0 ? (
        <button
          type="button"
          className="absolute bottom-3 left-1/2 flex h-7 -translate-x-1/2 items-center gap-1.5 rounded-full border border-border-strong bg-popover px-3 text-xs font-medium text-foreground shadow-md transition-colors hover:bg-accent"
          onClick={() => {
            if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
            setFollowTail(true);
          }}
        >
          <Icon name="chevron-down" className="h-3 w-3" />
          Jump to latest
        </button>
      ) : null}
    </div>
  );
}
