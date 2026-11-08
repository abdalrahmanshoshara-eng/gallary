import { describe, expect, it, vi } from "vitest";

vi.mock("@/i18n/navigation", () => ({ Link: () => null }));

import { voidOutcome } from "./AuctionManager";

const bid = (id: string, amount: string, status = "outbid", at = "2026-11-05T10:00:00Z") =>
  ({ id, amount, status, created_at: at, alias: 1, bidder: id, bidder_phone: "", void_reason: "" }) as Parameters<typeof voidOutcome>[1];

describe("voidOutcome", () => {
  const bids = [bid("top", "150.00", "valid"), bid("mid", "120.00"), bid("old", "200.00", "voided"), bid("low", "100.00")];
  it("names the bid that takes the lead back", () => {
    const outcome = voidOutcome(bids, bids[0]!);
    expect(outcome.kind).toBe("top");
    if (outcome.kind === "top") expect(outcome.next.id).toBe("mid");
  });
  it("says the price does not move for a lower bid", () => {
    expect(voidOutcome(bids, bids[3]!)).toEqual({ kind: "lower" });
  });
  it("returns to the opening price when the only bid goes", () => {
    expect(voidOutcome([bid("only", "100.00", "valid")], bid("only", "100.00", "valid"))).toEqual({ kind: "opening" });
  });
});
