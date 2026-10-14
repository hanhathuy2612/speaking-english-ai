import { describe, expect, it } from "vitest";
import { replayGain } from "./replay";

describe("replayGain", () => {
  it("brings a quiet recording up to about -1 dBFS", () => {
    expect(replayGain(0.09)).toBeCloseTo(10); // -21 dBFS peak
  });
  it("never boosts more than 12x, never turns a loud recording down", () => {
    expect(replayGain(0.01)).toBe(12);
    expect(replayGain(0.95)).toBe(1);
  });
  it("leaves silence and bad input alone", () => {
    expect(replayGain(0)).toBe(1);
    expect(replayGain(Number.NaN)).toBe(1);
  });
});
