import { describe, expect, it } from "vitest";
import { afterReading, sentenceKeys } from "./lesson";

describe("afterReading", () => {
  it("passes from 80% of the words", () => {
    expect(afterReading(0.8, 1)).toBe("good");
    expect(afterReading(1, 2)).toBe("good");
  });
  it("asks for one more try, then moves on", () => {
    expect(afterReading(0.5, 1)).toBe("retry");
    expect(afterReading(0.79, 2)).toBe("move_on");
  });
});

describe("sentenceKeys", () => {
  it("explains the sentence, then asks to read it", () => {
    expect(sentenceKeys(2)).toEqual(["s2", "read"]);
  });
});
