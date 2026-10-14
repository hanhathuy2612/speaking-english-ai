import type { FluencyRound } from "../api/types";
import type { Delta } from "./format";
import { fmtNum } from "./format";

/** Change from the first to the last measured round, e.g. "+18 từ/phút so với lần 1". */
export function roundDelta(rounds: FluencyRound[], key: "wpm_speaking" | "hesitations_per_100"): Delta | null {
  const vals = rounds.map((r) => r[key]).filter((v): v is number => v != null);
  if (vals.length < 2) return null;
  const diff = Math.round((vals[vals.length - 1] - vals[0]) * 10) / 10;
  const better = key === "wpm_speaking" ? diff > 0 : diff < 0;
  const sign = diff > 0 ? "+" : diff < 0 ? "−" : "±";
  return {
    text: `${sign}${fmtNum(Math.abs(diff))} so với lần 1`,
    tone: diff === 0 ? undefined : better ? "good" : "bad",
  };
}
