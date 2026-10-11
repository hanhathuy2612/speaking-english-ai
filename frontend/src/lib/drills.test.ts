import { describe, expect, it } from "vitest";
import { markFocus } from "./drills";

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
