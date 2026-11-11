/**
 * Chart kit (Recharts). Every chart in the product uses these pieces so they
 * share one palette, one tooltip, one axis style and one motion.
 *
 *   <ResponsiveContainer>
 *     <AreaChart data={rows} margin={CHART_MARGIN}>
 *       <defs><AreaFill id="g1" color={seriesColor(0)} /></defs>
 *       <CartesianGrid {...gridProps} />
 *       <XAxis dataKey="day" {...axisProps} />
 *       <YAxis {...axisProps} width={44} />
 *       <Tooltip content={<ChartTooltip />} cursor={cursorLine} />
 *       <Area dataKey="value" stroke={seriesColor(0)} fill="url(#g1)" {...lineProps} />
 *     </AreaChart>
 *   </ResponsiveContainer>
 *
 * Rules: blue first; a second series is light blue, a third is slate. Teal,
 * amber and violet only when there are four or more categories. Status
 * colours (green / amber / red) only when the data is a status.
 */
import * as React from 'react';
import { cn } from '@/lib/utils';

/** Ordered categorical palette, read from the design tokens. */
export const CHART_COLORS = [
  'hsl(var(--chart-1))', 'hsl(var(--chart-2))', 'hsl(var(--chart-3))',
  'hsl(var(--chart-4))', 'hsl(var(--chart-5))', 'hsl(var(--chart-6))',
];
export const seriesColor = (i: number) => CHART_COLORS[i % CHART_COLORS.length];

export const STATUS_COLORS = {
  success: 'hsl(var(--success))',
  warning: 'hsl(var(--warning))',
  danger: 'hsl(var(--destructive))',
  neutral: 'hsl(var(--chart-3))',
  info: 'hsl(var(--chart-1))',
};

export const CHART_MARGIN = { top: 8, right: 8, bottom: 0, left: 0 };

/** Spread on <XAxis> / <YAxis>. */
export const axisProps = {
  tick: { fontSize: 11, fill: 'hsl(var(--chart-axis))' },
  tickLine: false,
  axisLine: false,
  tickMargin: 8,
  minTickGap: 24,
} as const;

/** Spread on <CartesianGrid>. Horizontal hairlines only. */
export const gridProps = {
  vertical: false,
  stroke: 'hsl(var(--chart-grid))',
  strokeDasharray: '0',
} as const;

/** Spread on <Line> / <Area>. */
export const lineProps = {
  type: 'monotone' as const,
  strokeWidth: 2,
  dot: false,
  activeDot: { r: 4, strokeWidth: 2, stroke: 'hsl(var(--card))' },
  isAnimationActive: true,
  animationDuration: 900,
  animationEasing: 'ease-out' as const,
};

/** Spread on <Bar>. */
export const barProps = {
  radius: [4, 4, 0, 0] as [number, number, number, number],
  maxBarSize: 36,
  isAnimationActive: true,
  animationDuration: 800,
  animationEasing: 'ease-out' as const,
};

/** Tooltip `cursor` for line/area charts and for bar charts. */
export const cursorLine = { stroke: 'hsl(var(--border-strong))', strokeWidth: 1 };
export const cursorBand = { fill: 'hsl(var(--foreground) / 0.05)' };

/**
 * For charts that keep the built-in Recharts tooltip (custom formatter):
 * <Tooltip {...tooltipStyle} formatter={...} />. Readable in both themes.
 */
export const tooltipStyle = {
  contentStyle: {
    fontSize: 12,
    borderRadius: 8,
    border: '1px solid hsl(var(--border-strong))',
    background: 'hsl(var(--popover))',
    color: 'hsl(var(--popover-foreground))',
    boxShadow: '0 8px 24px hsl(0 0% 0% / 0.18)',
    padding: '8px 12px',
  },
  labelStyle: { color: 'hsl(var(--foreground))', fontWeight: 500, marginBottom: 4 },
  itemStyle: { color: 'hsl(var(--muted-foreground))', padding: 0 },
} as const;

/** Soft vertical gradient under an area series. Put inside <defs>. */
export function AreaFill({ id, color, from = 0.3 }: { id: string; color: string; from?: number }) {
  return (
    <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stopColor={color} stopOpacity={from} />
      <stop offset="100%" stopColor={color} stopOpacity={0} />
    </linearGradient>
  );
}

const fmt = (v: unknown) => {
  if (typeof v === 'number') return Math.abs(v) >= 1000 ? v.toLocaleString('en-US', { maximumFractionDigits: 1 }) : String(Math.round(v * 100) / 100);
  return String(v ?? '');
};
const pretty = (s: unknown) => String(s ?? '').replace(/[_-]+/g, ' ').replace(/^\w/, c => c.toUpperCase());

interface ChartTooltipProps {
  active?: boolean;
  payload?: any[];
  label?: unknown;
  /** Format a value (and optionally its series name). */
  valueFormatter?: (value: unknown, name?: string) => React.ReactNode;
  labelFormatter?: (label: unknown) => React.ReactNode;
  hideLabel?: boolean;
  className?: string;
}

/** Readable in both themes. Pass as <Tooltip content={<ChartTooltip />} />. */
export function ChartTooltip({ active, payload, label, valueFormatter, labelFormatter, hideLabel, className }: ChartTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;
  const title = labelFormatter ? labelFormatter(label) : label;
  return (
    <div className={cn('min-w-[128px] rounded-lg border border-border-strong bg-popover px-3 py-2 text-xs text-popover-foreground shadow-md', className)}>
      {!hideLabel && title !== undefined && title !== '' && <div className="mb-1.5 font-medium text-foreground">{title as React.ReactNode}</div>}
      <div className="space-y-1">
        {payload.map((p, i) => {
          const name = p.name ?? p.dataKey;
          const color = p.color || p.payload?.fill || p.stroke || seriesColor(i);
          return (
            <div key={`${name}-${i}`} className="flex items-center justify-between gap-4">
              <span className="flex min-w-0 items-center gap-2 text-muted-foreground">
                <span className="h-2 w-2 shrink-0 rounded-[2px]" style={{ background: color }} aria-hidden="true" />
                <span className="truncate">{pretty(name)}</span>
              </span>
              <span className="num shrink-0 font-medium text-foreground">{valueFormatter ? valueFormatter(p.value, String(name)) : fmt(p.value)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** Legend as quiet text chips. Use instead of the Recharts <Legend>. */
export function ChartLegend({ items, className }: { items: { label: React.ReactNode; color: string; value?: React.ReactNode }[]; className?: string }) {
  return (
    <ul className={cn('flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-muted-foreground', className)}>
      {items.map((it, i) => (
        <li key={i} className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-[2px]" style={{ background: it.color }} aria-hidden="true" />
          <span>{it.label}</span>
          {it.value !== undefined && <span className="num font-medium text-foreground">{it.value}</span>}
        </li>
      ))}
    </ul>
  );
}
