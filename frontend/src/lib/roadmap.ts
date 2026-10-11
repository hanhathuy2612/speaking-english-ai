import type { Topic, UnitStatus } from "../api/types";

/** Units in roadmap order (topic order, then unit order inside a topic). */
export const allUnits = (topics: Topic[]): UnitStatus[] => topics.flatMap((t) => t.units);

/**
 * The unit to open: the requested one if it exists, otherwise `next` (the server's next unit in the
 * open stages), otherwise the first unit not completed yet.
 */
export function pickUnit(topics: Topic[], requested: string | null, next: string | null = null): string | null {
  const units = allUnits(topics);
  if (requested && units.some((u) => u.id === requested)) return requested;
  if (next && units.some((u) => u.id === next)) return next;
  return (units.find((u) => !u.completed) ?? units[0])?.id ?? null;
}

export type UnitState = "done" | "started" | "new";

export const unitState = (u: UnitStatus): UnitState => (u.completed ? "done" : u.sessions ? "started" : "new");
