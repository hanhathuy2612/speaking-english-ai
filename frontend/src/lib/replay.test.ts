import { describe, expect, it } from "vitest";
import { replayGain } from "./replay";

describe("replayGain", () => {
  it("brings a fairly quiet recording up to about -6 dBFS", () => {
    expect(replayGain(0.25)).toBeCloseTo(2); // -12 dBFS peak
  });
  it("never boosts more than 3x, never turns a loud recording down", () => {
    expect(replayGain(0.05)).toBe(3);
    expect(replayGain(0.95)).toBe(1);
  });
  it("leaves silence and bad input alone", () => {
    expect(replayGain(0)).toBe(1);
    expect(replayGain(Number.NaN)).toBe(1);
  });
});
