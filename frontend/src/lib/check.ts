import type { CheckCriterion } from "../api/types";
import { fmtNum } from "./format";

/** 125 -> "2:05". */
export function fmtClock(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/** The measured value of one check criterion, as shown next to its label. */
export function criterionValue(c: CheckCriterion): string {
  switch (c.key) {
    case "duration":
      return `${fmtClock(c.value as number)} / ${fmtClock(c.target as number)}`;
    case "wpm_speaking":
      return c.value == null ? "Chưa đủ 10 từ để tính" : `${c.value} từ/phút`;
    case "hesitations_per_100":
      return c.value == null ? "–" : `${fmtNum(c.value as number)} lần`;
    case "english":
      return c.value ? "Có" : "Có đoạn không phải tiếng Anh";
  }
}
