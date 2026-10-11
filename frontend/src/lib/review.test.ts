import { describe, expect, it } from "vitest";
import { fmtDue, localDay } from "./review";

describe("fmtDue", () => {
  it("says when the card comes back", () => {
    expect(fmtDue("2026-10-11", "2026-10-11")).toBe("hôm nay");
    expect(fmtDue("2026-10-12", "2026-10-11")).toBe("ngày mai");
    expect(fmtDue("2026-10-18", "2026-10-11")).toBe("sau 7 ngày");
  });
});

describe("localDay", () => {
  it("formats the local date", () => {
    expect(localDay(new Date(2026, 0, 5, 23, 30))).toBe("2026-01-05");
  });
});
