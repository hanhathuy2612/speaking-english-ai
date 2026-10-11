import { describe, expect, it } from "vitest";
import type { CheckCriterion } from "../api/types";
import { criterionValue, fmtClock } from "./check";

const c = (key: CheckCriterion["key"], value: CheckCriterion["value"], target: CheckCriterion["target"]) =>
  ({ key, label: "", value, target, passed: false }) as CheckCriterion;

describe("fmtClock", () => {
  it("formats minutes and zero-padded seconds", () => {
    expect(fmtClock(125.7)).toBe("2:05");
    expect(fmtClock(9)).toBe("0:09");
    expect(fmtClock(-3)).toBe("0:00");
  });
});

describe("criterionValue", () => {
  it("shows each measured value in learner terms", () => {
    expect(criterionValue(c("duration", 95, 120))).toBe("1:35 / 2:00");
    expect(criterionValue(c("wpm_speaking", null, 110))).toBe("Chưa đủ 10 từ để tính");
    expect(criterionValue(c("hesitations_per_100", 4.2, 3))).toBe("4,2 lần");
    expect(criterionValue(c("english", false, true))).toBe("Có đoạn không phải tiếng Anh");
  });
});
