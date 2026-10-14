import { describe, expect, it } from "vitest";
import { moved, shiftPhrase, slugify, splitList } from "./content";

describe("slugify", () => {
  it("makes a backend-valid id", () => {
    expect(slugify("Your Weekend!")).toBe("your-weekend");
    expect(slugify("  I'm on a Trip -- to Đà Lạt ")).toBe("im-on-a-trip-to-da-lat");
    expect(slugify("???")).toBe("");
  });
});

describe("splitList", () => {
  it("drops empty parts", () => expect(splitList("a, b ,, c,")).toEqual(["a", "b", "c"]));
});

describe("moved", () => {
  it("swaps neighbours and ignores moves past the ends", () => {
    expect(moved([1, 2, 3], 0, 1)).toEqual([2, 1, 3]);
    expect(moved([1, 2, 3], 0, -1)).toEqual([1, 2, 3]);
  });
});

describe("shiftPhrase", () => {
  it("follows the phrases after a deletion", () => {
    expect(shiftPhrase(3, 1)).toBe(2);
    expect(shiftPhrase(0, 1)).toBe(0);
    expect(shiftPhrase(1, 1)).toBeNull();
  });
});
