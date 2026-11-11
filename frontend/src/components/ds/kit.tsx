/**
 * Building blocks for product screens.
 * ----------------------------------------------------------------------------
 * Screens are assembled from these, so every area shares one visual language
 * with the Nexus AI ontology product: quiet surfaces, hairlines, text-first
 * metrics, one blue accent. Presentational only: no data fetching in here.
 */
import * as React from "react";
import { createPortal } from "react-dom";

import { cn } from "@/lib/utils";
import { Icon, type IconName } from "@/components/ds/Icon";

/* ------------------------------------------------------------------- tones */

export type Tone = "neutral" | "info" | "success" | "warning" | "danger";

const TONE_TEXT: Record<Tone, string> = {
  neutral: "text-muted-foreground",
  info: "text-primary dark:text-brand-hi",
  success: "text-success",
  warning: "text-warning",
  danger: "text-destructive",
};
const TONE_BG: Record<Tone, string> = {
  neutral: "bg-border-strong",
  info: "bg-primary",
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-destructive",
};

/** Map any backend status word to a tone. Add words here, not in screens. */
export function toneOf(status?: string | null): Tone {
  const s = String(status || "").toLowerCase().replace(/[\s-]+/g, "_");
  if (/^(ok|pass|passed|success|succeeded|completed|complete|done|active|healthy|connected|enabled|available|verified|valid|online|up|true|ready|reprocessed)$/.test(s)) return "success";
  if (/^(running|in_progress|processing|executing|started|claimed|info|busy)$/.test(s)) return "info";
  if (/^(warn|warning|degraded|pending|paused|queued|queuing|waiting|partial|stale|skipped|unknown|dismissed)$/.test(s)) return "warning";
  if (/^(fail|failed|error|errored|critical|blocked|rejected|down|offline|expired|invalid|cancelled|canceled|disabled|false|breached|unhealthy|crashed)$/.test(s)) return "danger";
  return "neutral";
}

const LIVE = /^(running|in_progress|processing|executing|claimed|busy)$/;

/* ------------------------------------------------------------- StatusPill */

interface StatusPillProps extends React.HTMLAttributes<HTMLSpanElement> {
  /** Backend status word. Used for the tone and, if no children, the label. */
  status?: string | null;
  tone?: Tone;
  /** Pulse the dot (defaults to true for running-type statuses). */
  live?: boolean;
  /** "dot" = dot + text (default, quiet). "soft" = tinted pill for emphasis. */
  variant?: "dot" | "soft";
}

/** The one way to show a status anywhere in the product. */
export function StatusPill({ status, tone, live, variant = "dot", className, children, ...rest }: StatusPillProps) {
  const t = tone || toneOf(status);
  const key = String(status || "").toLowerCase().replace(/[\s-]+/g, "_");
  const isLive = live ?? LIVE.test(key);
  const label = children ?? String(status || "").replace(/[_-]+/g, " ").toLowerCase();
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap text-xs font-medium",
        variant === "soft"
          ? cn("rounded-md border px-2 py-0.5", {
              neutral: "border-border bg-surface-2 text-muted-foreground",
              info: "border-info/25 bg-info/10 text-info",
              success: "border-success/25 bg-success/10 text-success",
              warning: "border-warning/25 bg-warning/10 text-warning",
              danger: "border-destructive/25 bg-destructive/10 text-destructive",
            }[t])
          : "text-foreground",
        className,
      )}
      {...rest}
    >
      <span className={cn(isLive ? "dot-live" : "inline-block h-1.5 w-1.5 rounded-full bg-current", TONE_TEXT[t])} aria-hidden="true" />
      <span className="first-letter:uppercase">{label}</span>
    </span>
  );
}

/** "Live" / "Polling" indicator for screens fed by a server stream. */
export function LiveBadge({ live, className, ...rest }: { live: boolean; className?: string } & React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-xs font-medium", live ? "text-success" : "text-muted-foreground", className)} {...rest}>
      <span className={live ? "dot-live" : "inline-block h-1.5 w-1.5 rounded-full bg-current"} aria-hidden="true" />
      {live ? "Live" : "Polling"}
    </span>
  );
}

/* ------------------------------------------------------------- PageHeader */

interface PageHeaderProps {
  title: React.ReactNode;
  description?: React.ReactNode;
  /** Link back to the parent list (object pages). */
  back?: React.ReactNode;
  /** Status / badges shown beside the title. */
  meta?: React.ReactNode;
  /** Buttons / controls aligned to the right (stack below on phones). */
  actions?: React.ReactNode;
  className?: string;
}

/** The one page title block. Every routed page starts with this. */
export function PageHeader({ title, description, back, meta, actions, className }: PageHeaderProps) {
  return (
    <div className={cn("flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between", className)}>
      <div className="min-w-0">
        {back && <div className="mb-2 text-sm">{back}</div>}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <h2 className="text-xl font-medium tracking-tight text-foreground">{title}</h2>
          {meta}
        </div>
        {description && <p className="mt-1 max-w-3xl text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

/* ------------------------------------------------------------------ Panel */

interface PanelProps extends Omit<React.HTMLAttributes<HTMLElement>, "title"> {
  title?: React.ReactNode;
  description?: React.ReactNode;
  /** Controls on the right of the header. */
  actions?: React.ReactNode;
  footer?: React.ReactNode;
  /** No body padding: for tables and lists that run edge to edge. */
  flush?: boolean;
  bodyClassName?: string;
}

/** A titled surface. Use for one coherent object; never nest panels. */
export function Panel({ title, description, actions, footer, flush, className, bodyClassName, children, ...rest }: PanelProps) {
  return (
    <section className={cn("flex min-w-0 flex-col overflow-hidden rounded-xl border border-border bg-card shadow-xs", className)} {...rest}>
      {(title || actions) && (
        <header className="flex min-h-[52px] flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b border-border px-4 py-2.5 sm:px-5">
          <div className="min-w-0">
            {title && <h2 className="truncate text-md font-medium text-foreground">{title}</h2>}
            {description && <p className="truncate text-xs text-muted-foreground">{description}</p>}
          </div>
          {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={cn("min-h-0 flex-1", !flush && "p-4 sm:p-5", bodyClassName)}>{children}</div>
      {footer && <footer className="border-t border-border px-4 py-2.5 text-xs text-muted-foreground sm:px-5">{footer}</footer>}
    </section>
  );
}

/* ---------------------------------------------------------------- Toolbar */

/** Row of filters on the left and actions on the right (wraps on phones). */
export function Toolbar({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn("flex flex-wrap items-center gap-2.5", className)}>{children}</div>;
}
export function ToolbarSpacer() {
  return <div className="hidden flex-1 sm:block" />;
}

interface SearchInputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "onChange"> {
  value: string;
  onChange: (value: string) => void;
  className?: string;
}

export function SearchInput({ value, onChange, className, placeholder = "Search", ...rest }: SearchInputProps) {
  return (
    <div className={cn("relative w-full sm:w-64", className)}>
      <Icon name="search" className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-subtle-foreground" />
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
        className="field field-sm pl-9 pr-8"
        {...rest}
      />
      {value && (
        <button
          type="button"
          onClick={() => onChange("")}
          aria-label="Clear search"
          className="absolute right-2 top-1/2 flex h-5 w-5 -translate-y-1/2 items-center justify-center rounded text-subtle-foreground hover:text-foreground"
        >
          <Icon name="close" className="h-3 w-3" />
        </button>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ Chips */

export interface ChipOption<T extends string = string> {
  value: T;
  label: React.ReactNode;
  count?: number;
  testId?: string;
}

interface ChipsProps<T extends string> {
  options: ChipOption<T>[];
  value: T;
  onChange: (value: T) => void;
  label?: string;
  className?: string;
}

/** Single-select filter chips (statuses, windows, kinds). */
export function Chips<T extends string>({ options, value, onChange, label, className }: ChipsProps<T>) {
  return (
    <div role="tablist" aria-label={label} className={cn("scrollbar-hide flex min-w-0 gap-1 overflow-x-auto", className)}>
      {options.map((o) => {
        const on = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            role="tab"
            aria-selected={on}
            data-testid={o.testId}
            onClick={() => onChange(o.value)}
            className={cn(
              "inline-flex h-8 shrink-0 items-center gap-1.5 rounded-md px-2.5 text-sm transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              on ? "bg-accent font-medium text-foreground" : "text-muted-foreground hover:bg-accent/70 hover:text-foreground",
            )}
          >
            {o.label}
            {o.count != null && <span className={cn("num text-xs", on ? "text-muted-foreground" : "text-subtle-foreground")}>{o.count}</span>}
          </button>
        );
      })}
    </div>
  );
}

/** Compact segmented control (time windows, view switches). */
export function Segmented<T extends string>({ options, value, onChange, label, className }: ChipsProps<T>) {
  return (
    <div role="tablist" aria-label={label} className={cn("inline-flex shrink-0 items-center gap-0.5 rounded-lg border border-border bg-surface-2/60 p-0.5", className)}>
      {options.map((o) => {
        const on = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            role="tab"
            aria-selected={on}
            data-testid={o.testId}
            onClick={() => onChange(o.value)}
            className={cn(
              "h-7 rounded-md px-2.5 text-xs font-medium transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              on ? "bg-card text-foreground shadow-xs ring-1 ring-border" : "text-muted-foreground hover:text-foreground",
            )}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

/* -------------------------------------------------------------- Sparkline */

export function Sparkline({ data, tone = "info", className, fill = true }: { data: number[]; tone?: Tone; className?: string; fill?: boolean }) {
  const id = React.useId();
  if (!data || data.length < 2) return null;
  const w = 100, h = 28;
  const min = Math.min(...data), max = Math.max(...data);
  const span = max - min || 1;
  const pts = data.map((v, i) => [(i / (data.length - 1)) * w, h - 2 - ((v - min) / span) * (h - 4)] as const);
  const line = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className={cn("h-7 w-24", TONE_TEXT[tone], className)} aria-hidden="true">
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="currentColor" stopOpacity="0.28" />
          <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
        </linearGradient>
      </defs>
      {fill && <path d={`${line} L${w},${h} L0,${h} Z`} fill={`url(#${id})`} />}
      <path d={line} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

/* ------------------------------------------------------------ MetricStrip */

export interface Metric {
  label: string;
  value: React.ReactNode;
  /** Small line under the value: target, delta, unit. */
  hint?: React.ReactNode;
  tone?: Tone;
  spark?: number[];
  onClick?: () => void;
  testId?: string;
}

/**
 * Headline numbers as one strip divided by hairlines (not separate boxes).
 * 2 columns on phones, up to `columns` on desktop.
 */
export function MetricStrip({ items, columns = 4, className }: { items: Metric[]; columns?: 2 | 3 | 4 | 5 | 6; className?: string }) {
  const cols = { 2: "lg:grid-cols-2", 3: "lg:grid-cols-3", 4: "lg:grid-cols-4", 5: "sm:grid-cols-3 lg:grid-cols-5", 6: "sm:grid-cols-3 xl:grid-cols-6" }[columns];
  return (
    <dl className={cn("grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-border bg-border shadow-xs", cols, className)}>
      {items.map((m) => {
        const Tag = (m.onClick ? "button" : "div") as "div";
        return (
          <Tag
            key={m.label}
            {...(m.onClick ? { type: "button", onClick: m.onClick } as object : {})}
            className={cn("flex min-w-0 items-end justify-between gap-3 bg-card p-4 text-left sm:px-5", m.onClick && "transition-colors hover:bg-surface-2/70")}
          >
            <div className="min-w-0">
              <dt className="truncate text-sm text-muted-foreground">{m.label}</dt>
              <dd data-testid={m.testId} className={cn("num mt-1.5 truncate text-2xl font-medium tracking-tight", m.tone && m.tone !== "neutral" && m.tone !== "info" ? TONE_TEXT[m.tone] : "text-foreground")}>{m.value}</dd>
              {m.hint && <div className="mt-0.5 truncate text-xs text-muted-foreground">{m.hint}</div>}
            </div>
            {m.spark && <Sparkline data={m.spark} tone={m.tone && m.tone !== "neutral" ? m.tone : "info"} className="mb-1 shrink-0" />}
          </Tag>
        );
      })}
    </dl>
  );
}

/* ------------------------------------------------------------- KeyValues */

export interface KV {
  label: string;
  value: React.ReactNode;
  mono?: boolean;
}

/** Label / value rows divided by hairlines. `columns={2}` for wide areas. */
export function KeyValues({ items, columns = 1, className }: { items: KV[]; columns?: 1 | 2; className?: string }) {
  return (
    <dl className={cn(columns === 2 ? "grid gap-x-10 sm:grid-cols-2" : "", className)}>
      {items.map((kv) => (
        <div key={kv.label} className="flex items-baseline justify-between gap-4 border-b border-border py-2 text-sm last:border-b-0">
          <dt className="shrink-0 text-muted-foreground">{kv.label}</dt>
          <dd className={cn("min-w-0 truncate text-right text-foreground", kv.mono && "font-mono text-xs")}>{kv.value ?? "—"}</dd>
        </div>
      ))}
    </dl>
  );
}

/* ------------------------------------------------------------------ Meter */

export function Meter({ value, max = 100, tone = "info", className, label }: { value: number; max?: number; tone?: Tone; className?: string; label?: string }) {
  const pct = Math.max(0, Math.min(100, (value / (max || 1)) * 100));
  return (
    <div role="meter" aria-valuenow={value} aria-valuemin={0} aria-valuemax={max} aria-label={label} className={cn("h-1.5 w-full overflow-hidden rounded-full bg-surface-3", className)}>
      <div className={cn("h-full rounded-full transition-[width] duration-slow ease-brand-out", TONE_BG[tone])} style={{ width: `${pct}%` }} />
    </div>
  );
}

/* -------------------------------------------------------------- CodeBlock */

export function CodeBlock({ children, className, maxHeight = 320, wrap, ...rest }: { children: string; className?: string; maxHeight?: number; wrap?: boolean } & Omit<React.HTMLAttributes<HTMLDivElement>, "children">) {
  const [copied, setCopied] = React.useState(false);
  const copy = () => {
    navigator.clipboard?.writeText(children).then(() => {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1400);
    }).catch(() => {});
  };
  return (
    <div className={cn("group relative overflow-hidden rounded-lg border border-border bg-surface-2/70", className)} {...rest}>
      <button
        type="button"
        onClick={copy}
        aria-label="Copy"
        className="absolute right-2 top-2 flex h-7 items-center gap-1 rounded-md border border-border bg-card px-2 text-xs text-muted-foreground opacity-0 transition-opacity hover:text-foreground focus-visible:opacity-100 group-hover:opacity-100"
      >
        <Icon name={copied ? "check" : "copy"} className="h-3.5 w-3.5" /> {copied ? "Copied" : "Copy"}
      </button>
      <pre className={cn("scroll-thin overflow-auto p-3 font-mono text-xs leading-5 text-foreground", wrap && "whitespace-pre-wrap break-words")} style={{ maxHeight }}>{children}</pre>
    </div>
  );
}

/* ------------------------------------------------------- Overlays (portal) */

function useOverlay(open: boolean, onClose: () => void) {
  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);
}

interface DetailSheetProps {
  open: boolean;
  onClose: () => void;
  title: React.ReactNode;
  description?: React.ReactNode;
  /** Badges / status shown under the title. */
  meta?: React.ReactNode;
  /** Buttons pinned to the bottom. */
  footer?: React.ReactNode;
  /** Wider sheet for tables or code (default 520px). */
  wide?: boolean;
  children: React.ReactNode;
  testId?: string;
}

/** Right-hand sheet for inspecting one item without leaving the list. */
export function DetailSheet({ open, onClose, title, description, meta, footer, wide, children, testId }: DetailSheetProps) {
  useOverlay(open, onClose);
  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-50" data-testid={testId}>
      <button type="button" aria-label="Close panel" className="absolute inset-0 animate-fade-in cursor-default bg-black/55 backdrop-blur-[2px]" onClick={onClose} />
      <aside
        role="dialog"
        aria-modal="true"
        className={cn("absolute inset-y-0 right-0 flex w-full animate-slide-in-right flex-col border-l border-border bg-popover text-popover-foreground shadow-lg", wide ? "sm:max-w-[760px]" : "sm:max-w-[520px]")}
      >
        <div className="border-b border-border px-5 pb-4 pt-5 pr-12">
          <h2 className="text-lg font-medium leading-6">{title}</h2>
          {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
          {meta && <div className="mt-3 flex flex-wrap items-center gap-2">{meta}</div>}
          <button type="button" onClick={onClose} aria-label="Close" className="absolute right-3 top-4 flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground">
            <Icon name="close" className="h-3.5 w-3.5" />
          </button>
        </div>
        <div className="scroll-thin min-h-0 flex-1 overflow-y-auto px-5 py-5">{children}</div>
        {footer && <div className="flex flex-wrap items-center justify-end gap-2 border-t border-border px-5 py-3">{footer}</div>}
      </aside>
    </div>,
    document.body,
  );
}

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: React.ReactNode;
  description?: React.ReactNode;
  footer?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}

/** Centered dialog for short forms and confirmations. */
export function Modal({ open, onClose, title, description, footer, className, children }: ModalProps) {
  useOverlay(open, onClose);
  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button type="button" aria-label="Close dialog" className="absolute inset-0 animate-fade-in cursor-default bg-black/55 backdrop-blur-[3px]" onClick={onClose} />
      <div role="dialog" aria-modal="true" className={cn("relative flex max-h-[calc(100dvh-2rem)] w-full max-w-md animate-scale-in flex-col overflow-hidden rounded-xl border border-border bg-popover text-popover-foreground shadow-lg", className)}>
        <div className="border-b border-border px-5 py-4 pr-12">
          <h3 className="text-lg font-medium leading-6">{title}</h3>
          {description && <p className="mt-0.5 text-sm text-muted-foreground">{description}</p>}
          <button type="button" onClick={onClose} aria-label="Close" className="absolute right-3 top-3.5 flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground">
            <Icon name="close" className="h-3.5 w-3.5" />
          </button>
        </div>
        <div className="scroll-thin min-h-0 flex-1 overflow-y-auto px-5 py-4">{children}</div>
        {footer && <div className="flex flex-wrap items-center justify-end gap-2 border-t border-border px-5 py-3">{footer}</div>}
      </div>
    </div>,
    document.body,
  );
}

/** Heading for a block inside a sheet or a page column. */
export function SubHeading({ children, action, className }: { children: React.ReactNode; action?: React.ReactNode; className?: string }) {
  return (
    <div className={cn("mb-2 flex items-baseline justify-between gap-3", className)}>
      <h3 className="text-sm font-medium text-foreground">{children}</h3>
      {action}
    </div>
  );
}

/* ------------------------------------------------------------------ Field */

export function Field({ label, hint, htmlFor, children, className }: { label: React.ReactNode; hint?: React.ReactNode; htmlFor?: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("min-w-0", className)}>
      <label htmlFor={htmlFor} className="mb-1.5 block text-xs font-medium text-muted-foreground">{label}</label>
      {children}
      {hint && <p className="mt-1 text-xs text-subtle-foreground">{hint}</p>}
    </div>
  );
}

/* ---------------------------------------------------------------- Notices */

export function InlineError({ children, onRetry, className, ...rest }: { children: React.ReactNode; onRetry?: () => void; className?: string } & React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div role="alert" className={cn("flex items-start gap-2.5 rounded-lg border border-destructive/25 bg-destructive/10 px-3 py-2.5 text-sm text-destructive", className)} {...rest}>
      <Icon name="alert-triangle" className="mt-0.5" />
      <div className="min-w-0 flex-1 break-words">{children}</div>
      {onRetry && <button type="button" onClick={onRetry} className="shrink-0 font-medium underline underline-offset-4">Retry</button>}
    </div>
  );
}

export function Notice({ tone = "info", children, className, ...rest }: { tone?: Tone; children: React.ReactNode; className?: string } & React.HTMLAttributes<HTMLDivElement>) {
  const styles: Record<Tone, string> = {
    neutral: "border-border bg-surface-2/70 text-muted-foreground",
    info: "border-info/25 bg-info/10 text-foreground",
    success: "border-success/25 bg-success/10 text-success",
    warning: "border-warning/25 bg-warning/10 text-warning",
    danger: "border-destructive/25 bg-destructive/10 text-destructive",
  };
  const icon: Record<Tone, IconName> = { neutral: "info", info: "info", success: "check-circle", warning: "alert-triangle", danger: "alert-triangle" };
  return (
    <div className={cn("flex items-start gap-2.5 rounded-lg border px-3 py-2.5 text-sm", styles[tone], className)} {...rest}>
      <Icon name={icon[tone]} className={cn("mt-0.5", tone === "info" && "text-primary dark:text-brand-hi")} />
      <div className="min-w-0 flex-1 break-words">{children}</div>
    </div>
  );
}

/* ----------------------------------------------------------------- Tables */

/** Table wrapper: rounded, bordered, scrolls sideways on small screens. */
export function TableShell({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn("scroll-thin overflow-x-auto rounded-xl border border-border bg-card shadow-xs", className)}>{children}</div>;
}

/* --------------------------------------------------------------- Skeleton */

export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("shimmer rounded-md", className)} {...props} />;
}

/** Loading placeholder for a list or table body. */
export function SkeletonRows({ rows = 4, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn("space-y-2.5 p-4 sm:p-5", className)} aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-8" style={{ width: `${92 - (i % 3) * 14}%` }} />
      ))}
    </div>
  );
}

/* ------------------------------------------------------------- EmptyState */

interface EmptyStateProps {
  icon?: IconName;
  title: string;
  description?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
  /** No dashed frame: for use inside a Panel. */
  bare?: boolean;
}

export function EmptyState({ icon, title, description, action, className, bare }: EmptyStateProps) {
  return (
    <div className={cn("flex flex-col items-center justify-center px-6 py-10 text-center", !bare && "rounded-xl border border-dashed border-border-strong", className)}>
      {icon && <Icon name={icon} className="mb-3 h-6 w-6 text-subtle-foreground" />}
      <h3 className="text-md font-medium text-foreground">{title}</h3>
      {description && <p className="mt-1 max-w-md text-sm text-muted-foreground">{description}</p>}
      {action && <div className="mt-4 text-sm">{action}</div>}
    </div>
  );
}

/* ------------------------------------------------------------------- Tabs */

export interface TabDef<T extends string = string> {
  value: T;
  label: React.ReactNode;
  icon?: IconName;
  count?: number;
  testId?: string;
}

/** Line tabs (underline). `sticky` pins the row under the top bar. */
export function LineTabs<T extends string>({ tabs, value, onChange, label, className, actions }: { tabs: TabDef<T>[]; value: T; onChange: (v: T) => void; label?: string; className?: string; actions?: React.ReactNode }) {
  return (
    <div className={cn("flex items-stretch gap-4 border-b border-border", className)}>
      <div role="tablist" aria-label={label} className="scrollbar-hide -mb-px flex min-w-0 flex-1 items-stretch gap-6 overflow-x-auto">
        {tabs.map((t) => {
          const on = t.value === value;
          return (
            <button
              key={t.value}
              type="button"
              role="tab"
              aria-selected={on}
              data-testid={t.testId}
              onClick={() => onChange(t.value)}
              className={cn(
                "relative flex h-10 shrink-0 items-center gap-2 whitespace-nowrap text-sm font-medium transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                on ? "text-foreground" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {t.icon && <Icon name={t.icon} className={cn(on ? "text-primary dark:text-brand-hi" : "text-subtle-foreground")} />}
              {t.label}
              {t.count != null && <span className="num text-xs text-subtle-foreground">{t.count}</span>}
              <span className={cn("absolute inset-x-0 bottom-0 h-0.5 origin-center rounded-full bg-primary transition-transform duration-300 ease-brand-out", on ? "scale-x-100" : "scale-x-0")} />
            </button>
          );
        })}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2 pb-1">{actions}</div>}
    </div>
  );
}

/* --------------------------------------------------------------------- Kbd */

export function Kbd({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <kbd className={cn("inline-flex h-5 min-w-5 items-center justify-center rounded border border-border-strong bg-surface-2 px-1 font-mono text-[11px] font-medium text-muted-foreground", className)}>
      {children}
    </kbd>
  );
}
