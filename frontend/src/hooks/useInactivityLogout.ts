import { useCallback, useEffect, useRef } from "react";

const INACTIVITY_MS = 5 * 60 * 1000;
const LAST_ACTIVITY_KEY = "nexus-ai-engine-last-activity-at";

const ACTIVITY_EVENTS = ["mousedown", "keydown", "scroll", "touchstart", "click"] as const;

function readLastActivity(): number | null {
  try {
    const raw = sessionStorage.getItem(LAST_ACTIVITY_KEY);
    if (!raw) return null;
    const ts = Number(raw);
    return Number.isFinite(ts) ? ts : null;
  } catch {
    return null;
  }
}

function writeLastActivity(ts = Date.now()): void {
  try {
    sessionStorage.setItem(LAST_ACTIVITY_KEY, String(ts));
  } catch {
    /* ignore */
  }
}

function clearLastActivity(): void {
  try {
    sessionStorage.removeItem(LAST_ACTIVITY_KEY);
  } catch {
    /* ignore */
  }
}

type Options = {
  enabled: boolean;
  onTimeout: () => void;
  timeoutMs?: number;
};

/** Clears session after a period without pointer/keyboard/scroll activity. */
export function useInactivityLogout({
  enabled,
  onTimeout,
  timeoutMs = INACTIVITY_MS,
}: Options): void {
  const onTimeoutRef = useRef(onTimeout);
  onTimeoutRef.current = onTimeout;
  const firedRef = useRef(false);

  const touchActivity = useCallback(() => {
    if (!enabled || firedRef.current) return;
    writeLastActivity();
  }, [enabled]);

  const checkExpired = useCallback(() => {
    if (!enabled || firedRef.current) return false;

    const last = readLastActivity();
    if (last == null) {
      writeLastActivity();
      return false;
    }

    if (Date.now() - last >= timeoutMs) {
      firedRef.current = true;
      clearLastActivity();
      onTimeoutRef.current();
      return true;
    }

    return false;
  }, [enabled, timeoutMs]);

  useEffect(() => {
    if (!enabled) {
      firedRef.current = false;
      return;
    }

    firedRef.current = false;
    writeLastActivity();

    const onActivity = () => touchActivity();
    ACTIVITY_EVENTS.forEach((event) => {
      document.addEventListener(event, onActivity, { passive: true });
    });

    const onVisibility = () => {
      if (document.visibilityState === "visible") {
        checkExpired();
      }
    };
    document.addEventListener("visibilitychange", onVisibility);

    const interval = window.setInterval(() => {
      if (document.visibilityState === "visible") {
        checkExpired();
      }
    }, 30_000);

    return () => {
      ACTIVITY_EVENTS.forEach((event) => {
        document.removeEventListener(event, onActivity);
      });
      document.removeEventListener("visibilitychange", onVisibility);
      window.clearInterval(interval);
    };
  }, [enabled, touchActivity, checkExpired]);
}
