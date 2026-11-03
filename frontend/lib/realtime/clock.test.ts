import { describe, expect, it } from "vitest";

import { ServerClock } from "./clock";

describe("ServerClock", () => {
  it("estimates offset from the midpoint of the round trip", () => {
    const clock = new ServerClock();
    // Sent at 1000, received at 1200 (rtt 200): server said 5100 at the midpoint (1100).
    clock.addSample(1000, new Date(5100).toISOString(), 1200);
    expect(clock.offset).toBe(4000);
    expect(clock.now(2000)).toBe(6000);
  });

  it("keeps the most precise (lowest round-trip) sample", () => {
    const clock = new ServerClock();
    clock.addSample(0, new Date(1050).toISOString(), 100); // rtt 100 → offset 1000
    clock.addSample(0, new Date(9999).toISOString(), 900); // rtt 900 → ignored
    expect(clock.offset).toBe(1000);
  });

  it("ignores invalid samples", () => {
    const clock = new ServerClock();
    clock.addSample(100, "not-a-date", 200);
    clock.addSample(300, new Date(0).toISOString(), 200);
    expect(clock.hasSample).toBe(false);
  });
});
