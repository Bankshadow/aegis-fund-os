/**
 * Operations snapshot: reporting-currency valuation and reconciliation
 * exceptions surfaced read-only on the Portfolio and Reconciliation pages.
 *
 * Sources, in priority order (first hit wins), resolved by the server function:
 *   1. R2 object  (binding OPERATIONS_BUCKET, key AEGIS_OPERATIONS_SNAPSHOT_KEY
 *      or "operations_snapshot.json") — the production path; the Python
 *      daily-close pipeline uploads here, so the dashboard reflects real data
 *      without a redeploy.
 *   2. AEGIS_OPERATIONS_SNAPSHOT_JSON  (inline env var).
 *   3. AEGIS_OPERATIONS_SNAPSHOT_PATH  (local filesystem; dev only).
 *   4. Unconfigured demo fallback.
 *
 * Only a snapshot that is explicitly a persisted `ready`/`provisional` record is
 * accepted; anything else fails closed rather than passing demo data off as real.
 */

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

export const DEFAULT_SNAPSHOT_KEY = "operations_snapshot.json";

export const UNCONFIGURED_SNAPSHOT: OperationsSnapshot = {
  status: "unconfigured",
  source: "demo_fallback",
  generatedAt: null,
  fx: null,
  exceptions: [],
};

/** Parse and validate a raw snapshot string; throws unless it is a real record. */
export function parseOperationsSnapshot(raw: string): OperationsSnapshot {
  let snapshot: OperationsSnapshot;
  try {
    snapshot = JSON.parse(raw) as OperationsSnapshot;
  } catch {
    throw new Error("operations snapshot is not valid JSON");
  }
  if (!["ready", "provisional"].includes(snapshot.status) || snapshot.source !== "persisted_snapshot") {
    throw new Error("operations snapshot is not a persisted ready/provisional record");
  }
  return snapshot;
}

/** Minimal shape of a Cloudflare R2 bucket binding (get → object with text()). */
export type R2Like = {
  get(key: string): Promise<{ text(): Promise<string> } | null>;
};

export type SnapshotSources = {
  bucket?: R2Like;
  key?: string;
  inlineJson?: string;
  readPath?: () => Promise<string>;
};

/**
 * Resolve a snapshot from the configured sources in priority order. Returns the
 * unconfigured fallback only when nothing is configured; a configured-but-invalid
 * source throws (fail closed).
 */
export async function loadOperationsSnapshot(sources: SnapshotSources): Promise<OperationsSnapshot> {
  if (sources.bucket) {
    const object = await sources.bucket.get(sources.key?.trim() || DEFAULT_SNAPSHOT_KEY);
    if (object) return parseOperationsSnapshot(await object.text());
  }
  if (sources.inlineJson) return parseOperationsSnapshot(sources.inlineJson);
  if (sources.readPath) return parseOperationsSnapshot(await sources.readPath());
  return UNCONFIGURED_SNAPSHOT;
}
