import { describe, expect, it } from "vitest";

import { formatCountdown, formatDateTime } from "./datetime";
import { formatUsd } from "./money";

describe("formatUsd", () => {
  it("formats decimal strings with latin digits", () => {
    const text = formatUsd("1250.50");
    expect(text).toContain("1,250.5");
    expect(text).toContain("$");
    expect(text).not.toMatch(/[٠-٩]/);
  });

  it("rejects invalid amounts", () => {
    expect(() => formatUsd("abc")).toThrow(RangeError);
  });
});

describe("formatDateTime", () => {
  it("renders UTC instants in Damascus time (UTC+3)", () => {
    expect(formatDateTime("2026-11-03T09:00:00Z")).toContain("12:00");
  });
});

describe("formatCountdown", () => {
  it("formats and clamps", () => {
    expect(formatCountdown(65_000)).toBe("1:05");
    expect(formatCountdown(3_725_000)).toBe("1:02:05");
    expect(formatCountdown(-5)).toBe("0:00");
  });
});
