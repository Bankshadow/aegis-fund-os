import { createServerFn } from "@tanstack/react-start";

import {
  parseLoopLineageSnapshot,
  type LoopLineageSnapshot,
  unconfiguredLoopLineage,
} from "./loop-lineage";

export const getLoopLineageSnapshot = createServerFn({ method: "GET" }).handler(
  async (): Promise<LoopLineageSnapshot> => {
    const env = (globalThis as typeof globalThis & {
      process?: { env?: Record<string, string | undefined> };
    }).process?.env;
    const snapshotPath = env?.AEGIS_LOOP_SNAPSHOT_PATH;
    const raw = snapshotPath
      ? await (async () => {
          const fs = await import("node:fs/promises");
          return fs.readFile(snapshotPath, "utf8");
        })()
      : env?.AEGIS_LOOP_SNAPSHOT_JSON;
    if (!raw) return unconfiguredLoopLineage();
    try {
      return parseLoopLineageSnapshot(raw);
    } catch {
      throw new Error("configured Loop lineage is not a valid read-only snapshot");
    }
  },
);
