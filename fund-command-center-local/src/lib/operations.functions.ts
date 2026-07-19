import { createServerFn } from "@tanstack/react-start";
import { getRequest } from "@tanstack/react-start/server";
import {
  loadOperationsSnapshot,
  type OperationsSnapshot,
  type R2Like,
} from "./operations-snapshot.ts";

export type { OperationsSnapshot } from "./operations-snapshot.ts";

type SnapshotEnv = {
  OPERATIONS_BUCKET?: R2Like;
  AEGIS_OPERATIONS_SNAPSHOT_KEY?: string;
  AEGIS_OPERATIONS_SNAPSHOT_JSON?: string;
  AEGIS_OPERATIONS_SNAPSHOT_PATH?: string;
};

export const getOperationsSnapshot = createServerFn({ method: "GET" }).handler(
  async (): Promise<OperationsSnapshot> => {
    const runtimeEnv = (getRequest() as Request & {
      runtime?: { cloudflare?: { env?: SnapshotEnv } };
    }).runtime?.cloudflare?.env;
    const globalEnv = (globalThis as { __env__?: SnapshotEnv }).__env__;
    const processEnv = (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env;

    // R2 binding comes from the runtime/global env; string config may also live
    // on process.env (Nitro mirrors vars there).
    const bucket = runtimeEnv?.OPERATIONS_BUCKET ?? globalEnv?.OPERATIONS_BUCKET;
    const key =
      runtimeEnv?.AEGIS_OPERATIONS_SNAPSHOT_KEY ??
      globalEnv?.AEGIS_OPERATIONS_SNAPSHOT_KEY ??
      processEnv?.AEGIS_OPERATIONS_SNAPSHOT_KEY;
    const inlineJson =
      runtimeEnv?.AEGIS_OPERATIONS_SNAPSHOT_JSON ??
      globalEnv?.AEGIS_OPERATIONS_SNAPSHOT_JSON ??
      processEnv?.AEGIS_OPERATIONS_SNAPSHOT_JSON;
    const snapshotPath =
      runtimeEnv?.AEGIS_OPERATIONS_SNAPSHOT_PATH ??
      globalEnv?.AEGIS_OPERATIONS_SNAPSHOT_PATH ??
      processEnv?.AEGIS_OPERATIONS_SNAPSHOT_PATH;

    return loadOperationsSnapshot({
      bucket,
      key,
      inlineJson,
      readPath: snapshotPath
        ? async () => {
            const fs = await import("node:fs/promises");
            return fs.readFile(snapshotPath, "utf8");
          }
        : undefined,
    });
  },
);
