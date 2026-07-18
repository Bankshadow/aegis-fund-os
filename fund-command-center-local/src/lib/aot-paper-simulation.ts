import Decimal from "decimal.js-light";
import { AOT_PAPER_MARKET, buildAotPaperGrid, type AotPaperGridInput } from "./thai-equity-grid.ts";

export type SyntheticAotBar = { index: number; open: string; high: string; low: string; close: string; volume: number };
export type AotSimulationSeedResult = {
  seed: number;
  bars: SyntheticAotBar[];
  trainBars: number;
  holdoutBars: number;
  trainFillCandidates: number;
  holdoutFillCandidates: number;
  requiredOpeningInventoryShares: string;
};

const tick = new Decimal(AOT_PAPER_MARKET.tickSize);
const roundTick = (value: Decimal) => value.div(tick).toDecimalPlaces(0, Decimal.ROUND_HALF_UP).mul(tick);

const seededRandom = (seed: number) => {
  let state = seed >>> 0;
  return () => {
    state += 0x6d2b79f5;
    let value = state;
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
};

const normal = (random: () => number) => {
  const u = Math.max(random(), Number.EPSILON);
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * random());
};

export function generateSyntheticAotBars(referencePrice: string, seed: number, count = 120): SyntheticAotBar[] {
  if (!Number.isInteger(count) || count < 10) throw new Error("Synthetic simulation requires at least 10 bars");
  const random = seededRandom(seed);
  let close = roundTick(new Decimal(referencePrice));
  if (!close.gt(0)) throw new Error("Reference price must be positive");
  return Array.from({ length: count }, (_, index) => {
    const open = close;
    const nextClose = open.mul(new Decimal(1).add(new Decimal(normal(random)).mul("0.012")));
    close = roundTick(nextClose.gt(tick) ? nextClose : tick);
    const excursion = new Decimal(Math.abs(normal(random))).mul("0.006");
    const highBase = open.gt(close) ? open : close;
    const lowBase = open.lt(close) ? open : close;
    const lowValue = lowBase.mul(new Decimal(1).sub(excursion));
    const high = roundTick(highBase.mul(new Decimal(1).add(excursion)));
    const low = roundTick(lowValue.gt(tick) ? lowValue : tick);
    return { index, open: open.toFixed(2), high: high.toFixed(2), low: low.toFixed(2), close: close.toFixed(2), volume: Math.floor(500_000 + random() * 1_500_000) };
  });
}

export function runAotPaperGridSimulation(input: AotPaperGridInput, seeds = [101, 202, 303]): AotSimulationSeedResult[] {
  if (seeds.length < 3) throw new Error("Synthetic validation requires at least 3 seeds");
  const orders = buildAotPaperGrid(input);
  const openingInventory = orders.filter((order) => order.side === "SELL").reduce((sum, order) => sum.add(order.quantity), new Decimal(0));
  return seeds.map((seed) => {
    const bars = generateSyntheticAotBars(input.referencePrice, seed);
    const split = Math.floor(bars.length * 0.8);
    const fills = bars.map((bar) => orders.filter((order) => new Decimal(order.price).gte(bar.low) && new Decimal(order.price).lte(bar.high)).length);
    return {
      seed,
      bars,
      trainBars: split,
      holdoutBars: bars.length - split,
      trainFillCandidates: fills.slice(0, split).reduce((sum, count) => sum + count, 0),
      holdoutFillCandidates: fills.slice(split).reduce((sum, count) => sum + count, 0),
      requiredOpeningInventoryShares: openingInventory.toFixed(0),
    };
  });
}
