import { ChevronDown, ChevronRight } from "lucide-react";

import { WorkflowStatusIcon } from "@/components/stage/WorkflowStatusIcon";
import { cn } from "@/lib/utils";
import type { StepStatus } from "@/types/stageJobStream";
import type { StageJourneyStage } from "@/types/stageJourney";

export type SelectedStep = { stageId: string; stepId: string };

type Props = {
  stages: StageJourneyStage[];
  stageStatus: (stageId: string) => StepStatus | string;
  stepStatus: (stageId: string, stepId: string) => StepStatus | string;
  logCount: (stageId: string, stepId: string) => number;
  expandedStages: Record<string, boolean>;
  selectedStep: SelectedStep | null;
  onToggleStage: (stageId: string) => void;
  onSelectStep: (stageId: string, stepId: string) => void;
};

export function WorkflowTree({
  stages,
  stageStatus,
  stepStatus,
  logCount,
  expandedStages,
  selectedStep,
  onToggleStage,
  onSelectStep,
}: Props) {
  const ordered = [...stages].sort((a, b) => a.order - b.order);

  return (
    <nav className="rounded-md border border-border bg-card overflow-hidden" aria-label="Workflow stages">
      <div className="px-3 py-2 border-b border-border bg-muted/30 text-xs font-medium text-muted-foreground">
        Workflow
      </div>
      <ul className="py-1">
        {ordered.map((stage) => {
          const expanded = !!expandedStages[stage.id];
          const stStatus = stageStatus(stage.id);

          return (
            <li key={stage.id}>
              <button
                type="button"
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition-colors hover:bg-accent/60"
                onClick={() => onToggleStage(stage.id)}
              >
                {expanded ? (
                  <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
                ) : (
                  <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                )}
                <WorkflowStatusIcon status={stStatus} />
                <span className="truncate font-medium">{stage.name}</span>
                <span className="ml-auto text-xs text-muted-foreground shrink-0">{stage.steps.length} steps</span>
              </button>

              {expanded ? (
                <ul className="pb-1">
                  {stage.steps.map((step) => {
                    const isSelected =
                      selectedStep?.stageId === stage.id && selectedStep?.stepId === step.id;
                    const status = stepStatus(stage.id, step.id);
                    const logs = logCount(stage.id, step.id);

                    return (
                      <li key={step.id}>
                        <button
                          type="button"
                          className={cn(
                            "flex w-full items-center gap-2 py-2 pr-3 pl-10 text-left text-sm transition-colors hover:bg-accent/60",
                            isSelected && "bg-accent/50 border-l-2 border-primary",
                          )}
                          onClick={() => onSelectStep(stage.id, step.id)}
                        >
                          <ChevronRight className="h-3.5 w-3.5 shrink-0 text-transparent" aria-hidden />
                          <WorkflowStatusIcon status={status} />
                          <span className="truncate">{step.name}</span>
                          {logs > 0 ? (
                            <span className="ml-auto text-[10px] text-muted-foreground shrink-0">{logs} lines</span>
                          ) : null}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              ) : null}
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
