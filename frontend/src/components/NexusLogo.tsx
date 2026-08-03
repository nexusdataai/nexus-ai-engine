export function NexusLogo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden="true">
      <polygon
        points="16,2 30,9 30,23 16,30 2,23 2,9"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        className="text-primary"
      />
      <polygon points="16,8 24,12 24,20 16,24 8,20 8,12" fill="currentColor" className="text-primary/80" />
    </svg>
  );
}
