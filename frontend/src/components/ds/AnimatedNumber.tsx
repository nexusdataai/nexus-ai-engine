import { useEffect, useRef, useState } from 'react';

interface AnimatedNumberProps {
  value: number | null | undefined;
  /** Shown while the value is not loaded yet. */
  placeholder?: string;
  durationMs?: number;
  format?: (n: number) => string;
  className?: string;
}

const defaultFormat = (n: number) => Math.round(n).toLocaleString('en-US');

/**
 * Counts up to a number when it first appears or changes.
 * Falls back to an instant update when the user prefers reduced motion.
 */
export function AnimatedNumber({ value, placeholder = '—', durationMs = 900, format = defaultFormat, className }: AnimatedNumberProps) {
  const [display, setDisplay] = useState<number | null>(null);
  const fromRef = useRef(0);

  useEffect(() => {
    if (value == null || Number.isNaN(value)) {
      setDisplay(null);
      return;
    }
    const reduce = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    if (reduce) {
      fromRef.current = value;
      setDisplay(value);
      return;
    }
    const from = fromRef.current;
    const start = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs);
      const eased = 1 - Math.pow(1 - t, 4);
      setDisplay(from + (value - from) * eased);
      if (t < 1) raf = requestAnimationFrame(tick);
      else fromRef.current = value;
    };
    raf = requestAnimationFrame(tick);
    // Browsers pause animation frames in a background tab. Make sure the real
    // number is shown anyway, so the figure is never left at the placeholder.
    const settle = window.setTimeout(() => { fromRef.current = value; setDisplay(value); }, durationMs + 200);
    return () => { cancelAnimationFrame(raf); window.clearTimeout(settle); };
  }, [value, durationMs]);

  return <span className={className ? `num ${className}` : 'num'}>{display == null ? placeholder : format(display)}</span>;
}

export default AnimatedNumber;
