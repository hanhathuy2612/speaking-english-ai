import { describe, expect, it } from "vitest";
import { fmtNum, latestWithDelta, niceMax } from "./format";

describe("niceMax", () => {
  it("rounds up to a clean axis maximum", () => {
    expect(niceMax(111)).toBe(200);
    expect(niceMax(9.7)).toBe(10);
    expect(niceMax(2.2)).toBe(2.5);
    expect(niceMax(0)).toBe(1);
  });
});

describe("fmtNum", () => {
  it("uses a decimal comma and a dash for missing values", () => {
    expect(fmtNum(4.1)).toBe("4,1");
    expect(fmtNum(null)).toBe("–");
  });
});

describe("latestWithDelta", () => {
  it("is good when speed goes up", () => {
    const r = latestWithDelta([70, null, 101], false);
    expect(r.value).toBe(101);
    expect(r.delta).toEqual({ text: "+31 so với buổi đầu", tone: "good" });
  });
  it("is good when pauses go down", () => {
    expect(latestWithDelta([8.8, 4.1], true).delta.tone).toBe("good");
  });
  it("needs two values to compare", () => {
    expect(latestWithDelta([5], true).delta.tone).toBeUndefined();
    expect(latestWithDelta([null], true).value).toBeNull();
  });
});
