import { describe, expect, it } from "vitest";
import { bestTone, isNewBest, markFocus, passedCount } from "./drills";

describe("markFocus", () => {
  it("marks focus words ignoring case and punctuation", () => {
    expect(markFocus("Thank you, it failed.", ["thank", "failed"])).toEqual([
      { text: "Thank", focus: true },
      { text: "you,", focus: false },
      { text: "it", focus: false },
      { text: "failed.", focus: true },
    ]);
  });
});

describe("best reading", () => {
  const r = (focus_correct: number, correct: number) => ({ focus_correct, focus_total: 2, correct, total: 6 });
  it("ranks focus words before the whole sentence", () => {
    expect(isNewBest(r(2, 3), r(1, 6))).toBe(true);
    expect(isNewBest(r(1, 6), r(2, 3))).toBe(false);
    expect(isNewBest(r(2, 5), r(2, 4))).toBe(true);
  });
  it("counts a tie and a first reading as a new best", () => {
    expect(isNewBest(r(2, 4), r(2, 4))).toBe(true);
    expect(isNewBest(r(0, 0), undefined)).toBe(true);
  });
  it("colours a sentence by its best reading", () => {
    expect(bestTone(r(2, 3))).toBe("success");
    expect(bestTone(r(1, 6))).toBe("warning");
    expect(bestTone(undefined)).toBe("");
  });
});

describe("passedCount", () => {
  it("counts sentences whose best reading got every focus word", () => {
    const best = {
      a: { focus_correct: 2, focus_total: 2, correct: 5, total: 6 },
      b: { focus_correct: 1, focus_total: 2, correct: 6, total: 6 },
    };
    expect(passedCount([{ id: "a" }, { id: "b" }, { id: "c" }], best)).toBe(1);
    expect(passedCount([{ id: "a" }], undefined)).toBe(0);
  });
});
