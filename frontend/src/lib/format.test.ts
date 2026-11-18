import { describe, expect, it } from "vitest";
import { activeSegment, duration, hms, parseNumber, shuffle } from "./format";

describe("format", () => {
  it("hms", () => {
    expect(hms(5)).toBe("0:05");
    expect(hms(3725)).toBe("1:02:05");
  });
  it("duration", () => {
    expect(duration(45)).toBe("45 s");
    expect(duration(5400)).toBe("1 h 30");
  });
  it("activeSegment", () => {
    const s = [0, 5, 10, 20];
    expect(activeSegment(s, -1)).toBe(-1);
    expect(activeSegment(s, 7)).toBe(1);
    expect(activeSegment(s, 25)).toBe(3);
  });
  it("shuffle keeps elements", () => {
    const out = shuffle([1, 2, 3, 4, 5], 0.42);
    expect([...out].sort()).toEqual([1, 2, 3, 4, 5]);
    expect(shuffle([1, 2, 3, 4, 5], 0.42)).toEqual(out);
  });
  it("parseNumber accepts Belgian format", () => {
    expect(parseNumber("1 250,50")).toBe(1250.5);
  });
});
