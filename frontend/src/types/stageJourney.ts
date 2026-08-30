export type RegisteredStageStep = {
  id: string;
  name: string;
  description?: string;
};

export type RegisteredStage = {
  stage_id: string;
  name: string;
  description?: string;
  steps: RegisteredStageStep[];
};

export type StageJourneyStage = {
  id: string;
  name: string;
  description?: string;
  status: string;
  order: number;
  steps: RegisteredStageStep[];
};

export type StageJob = {
  id: string;
  journeyId: string;
  jobType?: "journey" | "stage" | string;
  stageIds?: string[];
  stageId: string;
  stageName?: string;
  currentStageId?: string;
  status: string;
  progress: number;
  triggeredBy?: string;
  startedAt?: string | null;
  endedAt?: string | null;
  duration?: string | null;
};

export type StageJourneyDetail = {
  id: string;
  name: string;
  description: string;
  status: string;
  capability?: string;
  summary: {
    totalJobs: number;
    completedJobs: number;
    runningJobs: number;
    failedJobs: number;
    overallProgress: number;
  };
  stages: StageJourneyStage[];
  jobs: StageJob[];
};

export type UnifiedRunRow =
  | {
      kind: "stage_job";
      id: string;
      journeyId: string;
      journeyName?: string;
      jobType?: string;
      stageIds?: string[];
      stageId?: string;
      status: string;
      startedAt?: string | null;
    }
  | {
      kind: "dsl_execution";
      id: string;
      journeyId: string;
      status: string;
    };
