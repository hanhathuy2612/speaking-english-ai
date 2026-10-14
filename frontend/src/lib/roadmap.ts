import type { Topic, UnitStatus } from "../api/types";

/** Units in roadmap order (topic order, then unit order inside a topic). */
export const allUnits = (topics: Topic[]): UnitStatus[] => topics.flatMap((t) => t.units);

/**
 * The unit to open: the requested one if it exists, otherwise `next` (the server's next unit in the
 * open stages), otherwise the first unit not done yet.
 */
export function pickUnit(topics: Topic[], requested: string | null, next: string | null = null): string | null {
  const units = allUnits(topics);
  if (requested && units.some((u) => u.id === requested)) return requested;
  if (next && units.some((u) => u.id === next)) return next;
  return (units.find((u) => !u.done) ?? units[0])?.id ?? null;
}

export type UnitState = "done" | "started" | "new";

/** Done needs both parts when the unit has a lesson (docs/features/lesson.md). */
export const unitState = (u: UnitStatus): UnitState =>
  u.done ? "done" : u.sessions || u.lesson_done ? "started" : "new";

/** Where a unit opens: its lesson overview when it has one, otherwise the practice room. */
export const unitLink = (u: Pick<UnitStatus, "id" | "lesson">): string =>
  u.lesson ? `/lesson/${encodeURIComponent(u.id)}` : `/?unit=${encodeURIComponent(u.id)}`;
