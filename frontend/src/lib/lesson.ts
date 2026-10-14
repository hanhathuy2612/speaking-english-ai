// Pure helpers for the lesson part of a unit (docs/features/lesson.md).

/** Share of reference words heard correctly for a reading to pass. */
export const PASS_ACCURACY = 0.8;
/** Readings per sentence before the teacher moves on anyway. */
export const MAX_ATTEMPTS = 2;

export type ReadingOutcome = "good" | "retry" | "move_on";

/** What the teacher says after the learner's `attempt`-th reading (1-based) of a sentence. */
export function afterReading(accuracy: number, attempt: number): ReadingOutcome {
  if (accuracy >= PASS_ACCURACY) return "good";
  return attempt < MAX_ATTEMPTS ? "retry" : "move_on";
}

/** Lines the teacher speaks to introduce sentence `i`: the explanation with the sentence, then the request to read it. */
export const sentenceKeys = (i: number): string[] => [`s${i}`, "read"];
