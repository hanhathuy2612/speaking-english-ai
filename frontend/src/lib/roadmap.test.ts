import { describe, expect, it } from "vitest";
import type { Topic, UnitStatus } from "../api/types";
import { pickUnit, unitLink, unitState } from "./roadmap";

const unit = (id: string, sessions = 0, completed = 0, lesson = false, lesson_done = 0): UnitStatus => ({
  id,
  title: id,
  goal: "",
  questions: 5,
  sessions,
  completed,
  last_at: null,
  lesson,
  lesson_done,
  done: completed > 0 && (!lesson || lesson_done > 0),
});
const topics: Topic[] = [
  { id: "a", title: "A", description: "", locked: false, units: [unit("a1", 2, 1), unit("a2", 1, 0)] },
  { id: "b", title: "B", description: "", locked: true, units: [unit("b1")] },
];

describe("pickUnit", () => {
  it("opens the requested unit when it exists", () => {
    expect(pickUnit(topics, "b1")).toBe("b1");
  });
  it("otherwise opens the first unit not done", () => {
    expect(pickUnit(topics, "missing")).toBe("a2");
    expect(pickUnit(topics, null)).toBe("a2");
  });
  it("prefers the server's next unit in the open stages", () => {
    expect(pickUnit(topics, null, "b1")).toBe("b1");
    expect(pickUnit(topics, "a1", "b1")).toBe("a1");
    expect(pickUnit(topics, null, "gone")).toBe("a2");
  });
  it("falls back to the first unit when all are done, and to null when there are none", () => {
    const done: Topic[] = [{ ...topics[0], units: [unit("x", 1, 1)] }];
    expect(pickUnit(done, null)).toBe("x");
    expect(pickUnit([], null)).toBeNull();
  });
  it("does not skip a unit whose role-play is done but whose lesson is not", () => {
    const t: Topic[] = [{ ...topics[0], units: [unit("l1", 1, 1, true, 0), unit("l2")] }];
    expect(pickUnit(t, null)).toBe("l1");
  });
});

describe("unitState", () => {
  it("is done once completed, started after any answered session", () => {
    expect(unitState(unit("x", 3, 1))).toBe("done");
    expect(unitState(unit("x", 1, 0))).toBe("started");
    expect(unitState(unit("x"))).toBe("new");
  });
  it("needs both parts of a unit with a lesson", () => {
    expect(unitState(unit("x", 1, 1, true, 0))).toBe("started");
    expect(unitState(unit("x", 0, 0, true, 1))).toBe("started");
    expect(unitState(unit("x", 1, 1, true, 1))).toBe("done");
  });
});

describe("unitLink", () => {
  it("opens the lesson overview when the unit has a lesson", () => {
    expect(unitLink({ id: "tell-me", lesson: true })).toBe("/lesson/tell-me");
    expect(unitLink({ id: "weekend", lesson: false })).toBe("/?unit=weekend");
  });
});
