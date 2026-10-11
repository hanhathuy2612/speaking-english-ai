import { describe, expect, it } from "vitest";
import { checkLevelText, requirementText } from "./stages";

describe("checkLevelText", () => {
  it("lists only the parts of the level that are set", () => {
    expect(checkLevelText({ seconds: 60, wpm_speaking: 80 })).toBe("nói liền 1:00, từ 80 từ/phút");
    expect(checkLevelText({ seconds: 90, wpm_speaking: 95, hesitations_per_100: 5 })).toBe(
      "nói liền 1:30, từ 95 từ/phút, dưới 5 lần ngập ngừng / 100 từ",
    );
  });
});

describe("requirementText", () => {
  it("shows drill accuracy with how many attempts are still missing", () => {
    const r = { kind: "drill_accuracy", target: 90, window: 20, attempts: 6, accuracy: 83, met: false } as const;
    expect(requirementText(r).value).toBe("83% · mới 6/20 câu");
    expect(requirementText({ ...r, attempts: 0, accuracy: null }).value).toBe("chưa tập · mới 0/20 câu");
    expect(requirementText({ ...r, attempts: 20, accuracy: 92, met: true }).value).toBe("92%");
  });
  it("shows the check that met the level, or the latest one", () => {
    const latest = { created_at: "", duration_s: 25.3, wpm_speaking: null, hesitations_per_100: null };
    const r = { kind: "check", target: { seconds: 60, wpm_speaking: 80 }, latest, met: false } as const;
    expect(requirementText(r).value).toBe("gần nhất: 0:25 · – từ/phút");
    expect(requirementText({ ...r, latest: null }).value).toBe("chưa làm");
  });
  it("counts units, sets and exercises", () => {
    expect(requirementText({ kind: "units", done: 2, total: 6, met: false }).value).toBe("2/6 bài");
  });
});
