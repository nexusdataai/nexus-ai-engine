import { cn } from '@/lib/utils';

/**
 * Nexus AI brand mark and wordmark (same artwork as the website).
 * The mark draws with currentColor for the letterform and the brand blue for
 * the diagonal, so it works on both themes without separate files.
 */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={cn('h-7 w-7 shrink-0 text-foreground', className)} aria-hidden="true" focusable="false">
      <path d="M7.5 24.5V7.5M24.5 24.5V7.5" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" fill="none" />
      <path d="M7.5 7.5 24.5 24.5" stroke="hsl(var(--brand))" strokeWidth="2.4" strokeLinecap="round" fill="none" />
      <circle cx="7.5" cy="7.5" r="3.1" fill="hsl(var(--logo-bg, var(--sidebar)))" stroke="currentColor" strokeWidth="2" />
      <circle cx="7.5" cy="24.5" r="3.1" fill="hsl(var(--logo-bg, var(--sidebar)))" stroke="currentColor" strokeWidth="2" />
      <circle cx="24.5" cy="7.5" r="3.1" fill="hsl(var(--logo-bg, var(--sidebar)))" stroke="currentColor" strokeWidth="2" />
      <circle cx="24.5" cy="24.5" r="3.1" fill="hsl(var(--logo-bg, var(--sidebar)))" stroke="currentColor" strokeWidth="2" />
      <circle cx="16" cy="16" r="3.6" fill="hsl(var(--brand))" />
    </svg>
  );
}

interface LogoProps {
  className?: string;
  markClassName?: string;
  /** Hide the wordmark (collapsed sidebar, favicon-sized placements). */
  markOnly?: boolean;
}

export function Logo({ className, markClassName, markOnly }: LogoProps) {
  return (
    <span className={cn('group/logo inline-flex items-center gap-2.5', className)}>
      <LogoMark className={cn('transition-transform duration-slow ease-brand-out group-hover/logo:-rotate-6 group-hover/logo:scale-105', markClassName)} />
      {!markOnly && (
        <span className="text-[17px] font-semibold leading-none tracking-[-0.03em] text-foreground">
          Nexus<span className="ml-px font-normal text-primary dark:text-brand-hi">AI</span>
        </span>
      )}
    </span>
  );
}

export default Logo;
