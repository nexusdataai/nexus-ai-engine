import { Icon } from "@/components/ds/Icon";
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

const DONE = ["completed", "success", "succeeded"];

/**
 * The journey as a vertical pipeline: stages are nodes on a rail, in run
 * order; each stage opens to its steps. The rail turns green behind work
 * that has finished.
 */
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
    <nav className="flex min-w-0 flex-col overflow-hidden rounded-xl border border-border bg-card shadow-xs" aria-label="Workflow stages">
      <div className="flex min-h-[52px] items-center justify-between border-b border-border px-4 sm:px-5">
        <h3 className="text-md font-medium text-foreground">Workflow</h3>
        <span className="num text-xs text-muted-foreground">{ordered.length} stages</span>
      </div>
      <ol className="scroll-thin min-h-0 flex-1 overflow-y-auto px-3 py-3">
        {ordered.map((stage, index) => {
          const expanded = !!expandedStages[stage.id];
          const stStatus = stageStatus(stage.id);
          const done = DONE.includes(String(stStatus).toLowerCase());
          const last = index === ordered.length - 1;

          return (
            <li key={stage.id} className="relative">
              {!last ? (
                <span
                  className={cn("absolute left-[19px] top-9 h-[calc(100%-28px)] w-px", done ? "bg-success/40" : "bg-border-strong")}
                  aria-hidden="true"
                />
              ) : null}
              <button
                type="button"
                aria-expanded={expanded}
                className="relative flex w-full items-center gap-3 rounded-md px-2 py-2 text-left text-sm transition-colors hover:bg-accent/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                onClick={() => onToggleStage(stage.id)}
              >
                <WorkflowStatusIcon status={stStatus} size="md" className="bg-card" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium text-foreground">{stage.name}</span>
                  <span className="block text-xs text-muted-foreground">{stage.steps.length} steps</span>
                </span>
                <Icon name={expanded ? "chevron-down" : "chevron-right"} className="h-3.5 w-3.5 text-subtle-foreground" />
              </button>

              {expanded ? (
                <ul className="mb-1 ml-[19px] space-y-px border-l border-transparent pl-5">
                  {stage.steps.map((step) => {
                    const isSelected =
                      selectedStep?.stageId === stage.id && selectedStep?.stepId === step.id;
                    const status = stepStatus(stage.id, step.id);
                    const logs = logCount(stage.id, step.id);

                    return (
                      <li key={step.id}>
                        <button
                          type="button"
                          aria-current={isSelected ? "true" : undefined}
                          className={cn(
                            "flex w-full items-center gap-2.5 rounded-md px-2 py-1.5 text-left text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                            isSelected ? "bg-accent font-medium text-foreground" : "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
                          )}
                          onClick={() => onSelectStep(stage.id, step.id)}
                        >
                          <WorkflowStatusIcon status={status} />
                          <span className="truncate">{step.name}</span>
                          {logs > 0 ? (
                            <span className="num ml-auto shrink-0 text-xs text-subtle-foreground">{logs} lines</span>
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
      </ol>
    </nav>
  );
}
