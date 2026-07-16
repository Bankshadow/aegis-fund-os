export type LoopExperiment = {
  sequence: number;
  experimentId: string;
  recordedAt: string;
  hypothesis: string;
  maker: string;
  target: "research" | "paper";
  candidates: string[];
  benchmarks: string[];
  datasets: string[];
  heldOutSplit: string;
  seedCount: number;
  maxTrials: number;
  trialCount: number | null;
  meanRobustScore: number | null;
  validationReports: Record<
    string,
    {
      fold_count: number;
      median_test_score: number;
      selection_failure_rate: number;
    }
  >;
  decision: "kill" | "revise" | "paper_review" | "unresolved";
  reasons: string[];
  codeHash: string;
  dataHashes: Record<string, string>;
  recordHash: string;
  previousHash: string | null;
  paperReview: {
    reviewedAt: string;
    experimentRecordHash: string;
    maker: string;
    reviewer: string;
    decision: "approved_for_paper" | "rejected";
    rationale: string;
    recordHash: string;
  } | null;
};

export type LoopDriftTask = {
  taskId: string;
  action: "open_research_task";
  strategy: string;
  dataset: string;
  observedAt: string;
  signals: string[];
  baseline: Record<string, number>;
  current: Record<string, number>;
};

export type LoopLineageSnapshot = {
  schemaVersion: 1;
  source: "verified_loop_lineage" | "demo_fallback";
  generatedAt: string | null;
  readOnly: true;
  integrity: {
    experimentChain: "verified" | "unconfigured";
    experimentRecordCount: number;
    memoryFileHash: string | null;
    driftQueueRecordCount: number;
    driftQueueFileHash: string | null;
    reviewChain: "verified" | "unconfigured";
    reviewRecordCount: number;
    reviewFileHash: string | null;
  };
  summary: {
    experimentCount: number;
    openDriftTaskCount: number;
    verdictCounts: Record<string, number>;
    reviewCounts: {
      approved_for_paper: number;
      rejected: number;
      pending: number;
    };
  };
  experiments: LoopExperiment[];
  driftTasks: LoopDriftTask[];
  capabilities: {
    canMutateStrategy: false;
    canApprovePaper: false;
    canPlaceOrder: false;
  };
};

export const unconfiguredLoopLineage = (): LoopLineageSnapshot => ({
  schemaVersion: 1,
  source: "demo_fallback",
  generatedAt: null,
  readOnly: true,
  integrity: {
    experimentChain: "unconfigured",
    experimentRecordCount: 0,
    memoryFileHash: null,
    driftQueueRecordCount: 0,
    driftQueueFileHash: null,
    reviewChain: "unconfigured",
    reviewRecordCount: 0,
    reviewFileHash: null,
  },
  summary: {
    experimentCount: 0,
    openDriftTaskCount: 0,
    verdictCounts: { kill: 0, revise: 0, paper_review: 0, unresolved: 0 },
    reviewCounts: { approved_for_paper: 0, rejected: 0, pending: 0 },
  },
  experiments: [],
  driftTasks: [],
  capabilities: {
    canMutateStrategy: false,
    canApprovePaper: false,
    canPlaceOrder: false,
  },
});

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

export function parseLoopLineageSnapshot(raw: string): LoopLineageSnapshot {
  const value: unknown = JSON.parse(raw);
  if (!isRecord(value)) throw new Error("snapshot must be an object");
  const capabilities = value.capabilities;
  const integrity = value.integrity;
  const summary = value.summary;
  if (
    value.schemaVersion !== 1 ||
    value.source !== "verified_loop_lineage" ||
    value.readOnly !== true ||
    typeof value.generatedAt !== "string" ||
    !isRecord(capabilities) ||
    capabilities.canMutateStrategy !== false ||
    capabilities.canApprovePaper !== false ||
    capabilities.canPlaceOrder !== false ||
    !isRecord(integrity) ||
    integrity.experimentChain !== "verified" ||
    !["verified", "unconfigured"].includes(String(integrity.reviewChain)) ||
    !isRecord(summary) ||
    !isRecord(summary.reviewCounts) ||
    !Array.isArray(value.experiments) ||
    !Array.isArray(value.driftTasks)
  ) {
    throw new Error("snapshot failed read-only lineage validation");
  }
  for (const experiment of value.experiments) {
    const review = isRecord(experiment) ? experiment.paperReview : null;
    if (
      !isRecord(experiment) ||
      typeof experiment.experimentId !== "string" ||
      !["research", "paper"].includes(String(experiment.target)) ||
      !["kill", "revise", "paper_review", "unresolved"].includes(
        String(experiment.decision),
      ) ||
      !Array.isArray(experiment.datasets) ||
      !Array.isArray(experiment.reasons)
    ) {
      throw new Error("snapshot contains an invalid experiment");
    }
    if (
      review !== null &&
      (!isRecord(review) ||
        !["approved_for_paper", "rejected"].includes(String(review.decision)) ||
        typeof review.reviewer !== "string" ||
        typeof review.maker !== "string" ||
        review.reviewer.toLowerCase() === review.maker.toLowerCase() ||
        review.experimentRecordHash !== experiment.recordHash ||
        typeof review.rationale !== "string" ||
        !review.rationale.trim())
    ) {
      throw new Error("snapshot contains an invalid paper review");
    }
  }
  for (const task of value.driftTasks) {
    if (
      !isRecord(task) ||
      task.action !== "open_research_task" ||
      typeof task.taskId !== "string" ||
      !Array.isArray(task.signals)
    ) {
      throw new Error("snapshot contains an invalid drift task");
    }
  }
  return value as LoopLineageSnapshot;
}
