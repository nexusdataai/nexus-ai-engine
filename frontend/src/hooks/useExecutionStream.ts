import { useEffect, useRef, useState } from "react";

export type StreamEvent = {
  type: string;
  job_id?: string;
  step_id?: string | null;
  data?: Record<string, unknown>;
  timestamp?: string;
};

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";

export function useExecutionStream(executionId: string | undefined) {
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const retryRef = useRef(0);

  useEffect(() => {
    if (!executionId) return;

    let es: EventSource | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let cancelled = false;

    const connect = () => {
      if (cancelled) return;
      const base = API_BASE || window.location.origin;
      es = new EventSource(`${base}/api/v1/executions/${executionId}/stream`);
      es.onopen = () => {
        retryRef.current = 0;
        setConnected(true);
      };
      es.onmessage = (msg) => {
        try {
          const parsed = JSON.parse(msg.data) as StreamEvent;
          setEvents((prev) => [...prev.slice(-300), parsed]);
        } catch {
          /* ignore malformed frames */
        }
      };
      es.onerror = () => {
        setConnected(false);
        es?.close();
        es = null;
        if (!cancelled) {
          const delay = Math.min(30_000, 1000 * 2 ** retryRef.current);
          retryRef.current += 1;
          timer = setTimeout(connect, delay);
        }
      };
    };

    connect();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
      es?.close();
      setConnected(false);
    };
  }, [executionId]);

  return { events, connected };
}
