const key = (w: string) => w.toLowerCase().replace(/[^a-z0-9']/g, "");

/** Words of a drill sentence, with its focus words marked (same matching as the backend: case and
 * punctuation ignored). */
export function markFocus(text: string, focus: string[]): { text: string; focus: boolean }[] {
  const keys = new Set(focus.map(key));
  return text
    .split(/\s+/)
    .filter(Boolean)
    .map((w) => ({ text: w, focus: keys.has(key(w)) }));
}

type Scored = { focus_correct: number; focus_total: number; correct: number; total: number };

/** How good a reading is: focus words first, then the whole sentence (same order as best_reading()). */
export function readingRank(r: Scored): [number, number] {
  return [r.focus_total ? r.focus_correct / r.focus_total : 1, r.total ? r.correct / r.total : 1];
}

/** True when `r` is at least as good as the previous best (a tie counts: the newer one is kept). */
export function isNewBest(r: Scored, previous: Scored | undefined): boolean {
  if (!previous) return true;
  const [a, b] = readingRank(r);
  const [c, d] = readingRank(previous);
  return a > c || (a === c && b >= d);
}

/** Dot colour for a sentence: all focus words right, some wrong, or not read yet. */
export function bestTone(r: Scored | undefined): "success" | "warning" | "" {
  if (!r) return "";
  return r.focus_correct === r.focus_total ? "success" : "warning";
}

/** Sentences of a set whose best reading has every focus word right ("8/8 câu đã đạt"). */
export function passedCount(sentences: { id: string }[], best: Record<string, Scored> | undefined): number {
  return sentences.filter((x) => bestTone(best?.[x.id]) === "success").length;
}
