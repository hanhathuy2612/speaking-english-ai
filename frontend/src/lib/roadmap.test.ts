import { describe, expect, it } from "vitest";
import type { Topic, UnitStatus } from "../api/types";
import { pickUnit, unitState } from "./roadmap";

const unit = (id: string, sessions = 0, completed = 0): UnitStatus => ({
  id,
  title: id,
  goal: "",
  questions: 5,
  sessions,
  completed,
  last_at: null,
});
const topics: Topic[] = [
  { id: "a", title: "A", description: "", units: [unit("a1", 2, 1), unit("a2", 1, 0)] },
  { id: "b", title: "B", description: "", units: [unit("b1")] },
];

describe("pickUnit", () => {
  it("opens the requested unit when it exists", () => {
    expect(pickUnit(topics, "b1")).toBe("b1");
  });
  it("otherwise opens the first unit not completed", () => {
    expect(pickUnit(topics, "missing")).toBe("a2");
    expect(pickUnit(topics, null)).toBe("a2");
  });
  it("falls back to the first unit when all are done, and to null when there are none", () => {
    const done: Topic[] = [{ ...topics[0], units: [unit("x", 1, 1)] }];
    expect(pickUnit(done, null)).toBe("x");
    expect(pickUnit([], null)).toBeNull();
  });
});

describe("unitState", () => {
  it("is done once completed, started after any answered session", () => {
    expect(unitState(unit("x", 3, 1))).toBe("done");
    expect(unitState(unit("x", 1, 0))).toBe("started");
    expect(unitState(unit("x"))).toBe("new");
  });
});
