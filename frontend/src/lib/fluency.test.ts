import { describe, expect, it } from "vitest";
import type { FluencyRound } from "../api/types";
import { roundDelta } from "./fluency";

const round = (n: number, wpm: number | null, hes: number | null): FluencyRound => ({
  round: n,
  limit_s: 240,
  text: "",
  words: 0,
  duration_s: 0,
  wpm_speaking: wpm,
  hesitations_per_100: hes,
  not_english: false,
});

describe("roundDelta", () => {
  it("compares the last measured round with the first", () => {
    const rounds = [round(1, 70, 6), round(2, 80, 4.5), round(3, 88, 3)];
    expect(roundDelta(rounds, "wpm_speaking")).toEqual({ text: "+18 so với lần 1", tone: "good" });
    expect(roundDelta(rounds, "hesitations_per_100")).toEqual({ text: "−3 so với lần 1", tone: "good" });
  });
  it("needs two measured rounds", () => {
    expect(roundDelta([round(1, 70, 6), round(2, null, null)], "wpm_speaking")).toBeNull();
  });
});
