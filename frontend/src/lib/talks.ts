/** Pure helpers of talk lessons and learning after a check (docs/features/talk-lessons.md). */

import { fmtClock } from "./check";
import { fmtNum } from "./format";

/** The next practice prompt: one never practised first, otherwise the one after `current`. */
export function nextPrompt<T extends { id: string }>(prompts: T[], practised: string[], current?: string): T {
  const fresh = prompts.find((p) => p.id !== current && !practised.includes(p.id));
  if (fresh) return fresh;
  const i = prompts.findIndex((p) => p.id === current);
  return prompts[(i + 1) % prompts.length];
}

type Measured = { duration_s: number; wpm_speaking: number | null; hesitations_per_100: number | null };

/** Rows comparing a talk with an earlier one; `better` tells which way is an improvement. */
export function compareTalks(now: Measured, before: Measured | null) {
  const row = (label: string, a: number | null, b: number | null | undefined, fmt: (v: number) => string, up: boolean) => ({
    label,
    now: a == null ? "–" : fmt(a),
    before: b == null ? null : fmt(b),
    better: a == null || b == null || a === b ? null : up ? a > b : a < b,
  });
  return [
    row("Nói liền", now.duration_s, before?.duration_s, fmtClock, true),
    row("Từ/phút khi nói", now.wpm_speaking, before?.wpm_speaking, (v) => fmtNum(v), true),
    row("Ngập ngừng / 100 từ", now.hesitations_per_100, before?.hesitations_per_100, (v) => fmtNum(v), false),
  ];
}
