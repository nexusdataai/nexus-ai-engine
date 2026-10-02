import { BatchSchedulesPanel } from "@/components/schedules/BatchSchedulesPanel";
import { ArchivedJobsSearch } from "@/components/schedules/ArchivedJobsSearch";

export function SchedulesPage() {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold">Batch schedules</h2>
        <p className="text-sm text-muted-foreground">
          Periodic journey or stage runs. Timezone is stored only; fire time is UTC.
        </p>
      </div>
      <BatchSchedulesPanel />
      <ArchivedJobsSearch />
    </div>
  );
}
