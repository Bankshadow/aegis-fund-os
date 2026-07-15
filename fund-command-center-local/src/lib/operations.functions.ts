import { createServerFn } from "@tanstack/react-start";

export type OperationsSnapshot = {
  schemaVersion?: number;
  status: "ready" | "provisional" | "unconfigured";
  source: "persisted_snapshot" | "demo_fallback";
  generatedAt: string | null;
  fx: {
    reportingCurrency: string;
    asOf: string;
    status: "Approved" | "Provisional";
    totalBaseValue: number;
    rates: Array<{ pair: string; rate: number; status: "Approved" | "Provisional" }>;
  } | null;
  exceptions: Array<{
    id: string;
    asset: string;
    reason: string;
    owner: string;
    status: "Open" | "Resolved";
    approvedBy?: string;
  }>;
};

export const getOperationsSnapshot = createServerFn({ method: "GET" }).handler(
  async (): Promise<OperationsSnapshot> => {
    const env = (globalThis as typeof globalThis & {
      process?: { env?: Record<string, string | undefined> };
    }).process?.env;
    const snapshotPath = env?.AEGIS_OPERATIONS_SNAPSHOT_PATH;
    const raw = snapshotPath
      ? await (async () => {
          const fs = await import("node:fs/promises");
          return fs.readFile(snapshotPath, "utf8");
        })()
      : env?.AEGIS_OPERATIONS_SNAPSHOT_JSON;
    if (!raw) {
      return {
        status: "unconfigured",
        source: "demo_fallback",
        generatedAt: null,
        fx: null,
        exceptions: [],
      };
    }
    try {
      const snapshot = JSON.parse(raw) as OperationsSnapshot;
      if (!["ready", "provisional"].includes(snapshot.status) || snapshot.source !== "persisted_snapshot") {
        throw new Error("invalid operations snapshot status");
      }
      return snapshot;
    } catch {
      throw new Error("AEGIS_OPERATIONS_SNAPSHOT_JSON is not a valid persisted snapshot");
    }
  },
);
