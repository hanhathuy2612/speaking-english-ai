import { describe, expect, it } from "vitest";
import { compareTalks, nextPrompt, splitUnsure } from "./talks";

const prompts = [{ id: "a" }, { id: "b" }, { id: "c" }];

describe("nextPrompt", () => {
  it("prefers prompts never practised, then goes round", () => {
    expect(nextPrompt(prompts, ["a"]).id).toBe("b");
    expect(nextPrompt(prompts, ["a", "b"], "c").id).toBe("a"); // c is on screen: the next one
    expect(nextPrompt(prompts, ["a", "b", "c"], "c").id).toBe("a");
    expect(nextPrompt(prompts, ["a", "b", "c"], "a").id).toBe("b");
  });
});

describe("compareTalks", () => {
  it("marks longer, faster and fewer hesitations as better", () => {
    const [time, speed, pauses] = compareTalks(
      { duration_s: 75, wpm_speaking: 90, hesitations_per_100: 6.5 },
      { duration_s: 54, wpm_speaking: 81, hesitations_per_100: 9.6 },
    );
    expect(time).toEqual({ label: "Nói liền", now: "1:15", before: "0:54", better: true });
    expect(speed.better).toBe(true);
    expect(pauses).toEqual({ label: "Ngập ngừng / 100 từ", now: "6,5", before: "9,6", better: true });
  });
  it("has nothing to compare without an earlier talk or a measured value", () => {
    const rows = compareTalks({ duration_s: 20, wpm_speaking: null, hesitations_per_100: null }, null);
    expect(rows.map((r) => [r.now, r.before, r.better])).toEqual([
      ["0:20", null, null],
      ["–", null, null],
      ["–", null, null],
    ]);
  });
});

describe("splitUnsure", () => {
  it("marks the unsure sentences and keeps the rest", () => {
    expect(splitUnsure("A b. C d. E f.", ["C d."])).toEqual([
      { text: "A b. ", unsure: false },
      { text: "C d.", unsure: true },
      { text: " E f.", unsure: false },
    ]);
  });
  it("ignores sentences it cannot find", () => {
    expect(splitUnsure("A b.", ["X y."])).toEqual([{ text: "A b.", unsure: false }]);
  });
});
