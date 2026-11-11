import { useState } from "react";

import { LineTabs, PageHeader } from "@/components/ds/kit";
import { ArchivedJobsSearch } from "@/components/schedules/ArchivedJobsSearch";
import { BatchSchedulesPanel } from "@/components/schedules/BatchSchedulesPanel";

export function SchedulesPage() {
  const [tab, setTab] = useState<"schedules" | "archive">("schedules");
  return (
    <div className="space-y-5">
      <PageHeader
        title="Batch schedules"
        description="Periodic journey or stage runs. Timezone is stored only; fire time is UTC."
      />
      <LineTabs
        label="Schedules"
        value={tab}
        onChange={setTab}
        tabs={[
          { value: "schedules", label: "Schedules", icon: "calendar" },
          { value: "archive", label: "Archived jobs", icon: "folder" },
        ]}
      />
      {tab === "schedules" ? <BatchSchedulesPanel /> : <ArchivedJobsSearch />}
    </div>
  );
}
