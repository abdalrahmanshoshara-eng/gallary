import { describe, expect, it } from "vitest";

import { fromDamascusInput, toDamascusInput } from "@/lib/formatters/datetime";

import { applyMessage, mergeBids, normalizeAmount, phaseOf, quickAmounts, type AuctionState } from "./live";

const base = (over: Partial<AuctionState> = {}): AuctionState => ({
  seq: 5,
  server_time: "2026-11-05T10:00:00Z",
  status: "live",
  outcome: "",
  current_price: "100.00",
  minimum_next_bid: "110.00",
  bid_count: 1,
  starts_at: "2026-11-05T09:00:00Z",
  ends_at: "2026-11-05T12:00:00Z",
  extensions_count: 0,
  reserve_met: null,
  payment_deadline: null,
  winner_alias: null,
  bids: [{ id: "b1", amount: "100.00", alias: 1, created_at: "2026-11-05T09:30:00Z" }],
  me: { alias: 1, my_top_bid: "100.00", is_highest: true, is_winner: false, order_number: null, can_bid: false },
  ...over,
});
const bidMsg = (seq: number, amount: string, alias: number, extra: Record<string, unknown> = {}) => ({
  type: "bid.placed",
  seq,
  data: {
    current_price: amount,
    minimum_next_bid: (Number(amount) + 10).toFixed(2),
    bid_count: 2,
    bid: { id: `b${seq}`, amount, alias, created_at: "2026-11-05T10:01:00Z" },
    ...extra,
  },
});

describe("applyMessage", () => {
  it("applies the next message in order and tells the viewer they were outbid", () => {
    const result = applyMessage(base(), bidMsg(6, "120.00", 2));
    expect(result.kind).toBe("applied");
    if (result.kind !== "applied") return;
    expect(result.state.seq).toBe(6);
    expect(result.state.current_price).toBe("120.00");
    expect(result.state.minimum_next_bid).toBe("130.00");
    expect(result.state.bids.map((b) => b.amount)).toEqual(["120.00", "100.00"]);
    expect(result.state.me?.is_highest).toBe(false);
    expect(result.state.me?.my_top_bid).toBe("100.00");
    expect(result.event).toMatchObject({ type: "bid", mine: false });
  });

  it("recognises the viewer's own bid by alias", () => {
    const result = applyMessage(base({ me: { ...base().me!, is_highest: false } }), bidMsg(6, "130.00", 1));
    if (result.kind !== "applied") throw new Error("expected applied");
    expect(result.state.me?.is_highest).toBe(true);
    expect(result.state.me?.my_top_bid).toBe("130.00");
    expect(result.event).toMatchObject({ mine: true });
  });

  it("drops stale or duplicate messages and asks for a resync on a gap", () => {
    expect(applyMessage(base(), bidMsg(5, "120.00", 2)).kind).toBe("ignored");
    expect(applyMessage(base(), bidMsg(3, "120.00", 2)).kind).toBe("ignored");
    expect(applyMessage(base(), bidMsg(8, "120.00", 2)).kind).toBe("resync");
    expect(applyMessage(base(), { type: "pong", data: {} }).kind).toBe("ignored");
  });

  it("takes a newer snapshot but keeps the viewer's own position", () => {
    const result = applyMessage(base(), { type: "auction.snapshot", seq: 9, data: { ...base(), seq: 9, current_price: "300.00", me: undefined } });
    if (result.kind !== "applied") throw new Error("expected applied");
    expect(result.state.seq).toBe(9);
    expect(result.state.current_price).toBe("300.00");
    expect(result.state.me?.alias).toBe(1);
  });

  it("removes a voided bid and asks the caller to refresh the viewer's position", () => {
    const state = base({ bids: [{ id: "b2", amount: "150.00", alias: 2, created_at: "2026-11-05T09:40:00Z" }, ...base().bids] });
    const result = applyMessage(state, { type: "bid.voided", seq: 6, data: { voided_bid: "b2", current_price: "100.00", minimum_next_bid: "110.00", bid_count: 1 } });
    if (result.kind !== "applied") throw new Error("expected applied");
    expect(result.state.bids.map((b) => b.id)).toEqual(["b1"]);
    expect(result.state.current_price).toBe("100.00");
    expect(result.event).toEqual({ type: "voided", bidId: "b2" });
  });

  it("reports status changes", () => {
    const result = applyMessage(base(), { type: "auction.ended", seq: 6, data: { status: "pending_winner_payment", winner_alias: 1 } });
    if (result.kind !== "applied") throw new Error("expected applied");
    expect(result.event).toEqual({ type: "status", status: "pending_winner_payment" });
    expect(result.state.winner_alias).toBe(1);
  });
});

describe("helpers", () => {
  it("merges bids highest first without duplicates", () => {
    const bids = base().bids;
    const next = mergeBids(bids, { id: "b2", amount: "150.00", alias: 3, created_at: "2026-11-05T10:00:00Z" });
    expect(next.map((b) => b.id)).toEqual(["b2", "b1"]);
    expect(mergeBids(next, next[0]!)).toBe(next);
  });

  it("derives the phase from the server clock", () => {
    const s = base();
    expect(phaseOf(s, Date.parse("2026-11-05T08:00:00Z"))).toBe("upcoming");
    expect(phaseOf(s, Date.parse("2026-11-05T11:00:00Z"))).toBe("live");
    expect(phaseOf(s, Date.parse("2026-11-05T12:00:01Z"))).toBe("closing");
    expect(phaseOf({ ...s, status: "pending_winner_payment" }, 0)).toBe("pending_payment");
    expect(phaseOf({ ...s, status: "awarded" }, 0)).toBe("ended");
    expect(phaseOf({ ...s, status: "cancelled" }, 0)).toBe("cancelled");
  });

  it("offers +1×, +2×, +5× quick amounts", () => {
    expect(quickAmounts("110.00", "10.00")).toEqual(["110.00", "120.00", "150.00"]);
  });

  it("normalises typed amounts including Arabic digits", () => {
    expect(normalizeAmount("1,250.5")).toBe("1250.50");
    expect(normalizeAmount("١٢٥٠")).toBe("1250.00");
    expect(normalizeAmount(" 99 ")).toBe("99.00");
    expect(normalizeAmount("0")).toBeNull();
    expect(normalizeAmount("12.345")).toBeNull();
    expect(normalizeAmount("abc")).toBeNull();
  });

  it("converts Damascus wall time to instants and back", () => {
    expect(toDamascusInput("2026-11-05T09:30:00Z")).toBe("2026-11-05T12:30");
    expect(fromDamascusInput("2026-11-05T12:30")).toBe("2026-11-05T09:30:00.000Z");
    expect(fromDamascusInput("bad")).toBeNull();
  });
});
