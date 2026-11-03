import { describe, expect, it } from "vitest";

import { backoffDelay } from "./backoff";

describe("backoffDelay", () => {
  const options = { baseMs: 1000, maxMs: 30_000 };

  it("grows exponentially up to the cap", () => {
    const max = () => 1;
    expect(backoffDelay(0, options, max)).toBe(1000);
    expect(backoffDelay(3, options, max)).toBe(8000);
    expect(backoffDelay(10, options, max)).toBe(30_000);
  });

  it("applies full jitter", () => {
    expect(backoffDelay(3, options, () => 0)).toBe(0);
    expect(backoffDelay(3, options, () => 0.5)).toBe(4000);
  });
});
