import { EmptyState } from "@/components/ds/kit";

export function ComingSoonPanel({ title }: { title: string }) {
  return (
    <EmptyState
      icon="clock"
      title={title}
      description="This view is not available yet."
      action={<span className="text-muted-foreground">Coming soon.</span>}
      className="py-16"
    />
  );
}
