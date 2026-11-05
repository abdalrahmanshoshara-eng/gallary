/**
 * Pure live-state logic for one auction (ARCHITECTURE §5.4), kept free of React and the
 * socket so every rule is unit-tested:
 * - stream messages are applied strictly in `seq` order; stale ones are dropped;
 * - a gap (missed message) asks the caller to resync from REST, never to guess;
 * - the viewer's own position is derived from the stable bidder alias.
 */
import type { Schema } from "@/lib/api/types";

export type AuctionState = Schema<"AuctionState">;
export type AuctionSnapshot = Omit<AuctionState, "me">;
export type PublicBid = Schema<"PublicBid">;
export type MyAuctionState = Schema<"MyAuctionState">;

export const OPEN_STATUSES = new Set(["scheduled", "live"]);
const MAX_BIDS = 20;

export type StreamMessage = { type: string; seq?: number; data: Record<string, unknown> };

export type ApplyResult =
  | { kind: "applied"; state: AuctionState; event: LiveEvent | null }
  | { kind: "ignored" }
  | { kind: "resync" };

/** What happened, for announcements and notices in the UI. */
export type LiveEvent =
  | { type: "bid"; bid: PublicBid; mine: boolean; extended: boolean }
  | { type: "status"; status: string }
  | { type: "updated" };

const STATE_FIELDS = [
  "status",
  "outcome",
  "current_price",
  "minimum_next_bid",
  "bid_count",
  "starts_at",
  "ends_at",
  "extensions_count",
  "reserve_met",
  "payment_deadline",
  "winner_alias",
] as const;

function pickState(data: Record<string, unknown>): Partial<AuctionState> {
  const out: Record<string, unknown> = {};
  for (const key of STATE_FIELDS) if (key in data) out[key] = data[key];
  return out as Partial<AuctionState>;
}

function isBid(value: unknown): value is PublicBid {
  if (!value || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  return typeof v.id === "string" && typeof v.amount === "string" && typeof v.alias === "number";
}

/** Highest first, newest first among equals; capped like the server snapshot. */
export function mergeBids(bids: PublicBid[], bid: PublicBid): PublicBid[] {
  if (bids.some((b) => b.id === bid.id)) return bids;
  return [bid, ...bids]
    .sort((a, b) => Number(b.amount) - Number(a.amount) || Date.parse(b.created_at) - Date.parse(a.created_at))
    .slice(0, MAX_BIDS);
}

/**
 * The viewer's position after a bid they may not have made: the alias is stable per bidder,
 * so the newest top bid tells whether they still lead. Eligibility to bid (customer
 * account, open window) is decided by the UI from the account and the clock.
 */
export function deriveMe(me: MyAuctionState | null, lastBid?: PublicBid): MyAuctionState | null {
  if (!me || !lastBid) return me;
  const isHighest = me.alias !== null && lastBid.alias === me.alias;
  return { ...me, is_highest: isHighest, my_top_bid: isHighest ? lastBid.amount : me.my_top_bid };
}

export function applyMessage(state: AuctionState, message: StreamMessage): ApplyResult {
  if (message.type === "auction.snapshot") {
    if (message.seq === undefined || message.seq < state.seq) return { kind: "ignored" };
    const snapshot = message.data as unknown as AuctionSnapshot;
    // The public snapshot never carries the viewer's position: keep ours (REST resync refreshes it).
    const next = { ...state, ...snapshot, seq: message.seq, me: state.me };
    return { kind: "applied", state: next, event: null };
  }
  if (message.seq === undefined) return { kind: "ignored" };
  if (message.seq <= state.seq) return { kind: "ignored" };
  if (message.seq > state.seq + 1) return { kind: "resync" };

  const base = { ...state, ...pickState(message.data), seq: message.seq };
  if (message.type === "bid.placed" && isBid(message.data.bid)) {
    const bid = message.data.bid;
    const next = { ...base, bids: mergeBids(state.bids, bid) };
    const mine = state.me?.alias !== null && state.me?.alias === bid.alias;
    return {
      kind: "applied",
      state: { ...next, me: deriveMe(state.me, bid) },
      event: { type: "bid", bid, mine, extended: message.data.extended === true },
    };
  }
  const statusChanged = base.status !== state.status;
  return {
    kind: "applied",
    state: base,
    event: statusChanged ? { type: "status", status: base.status } : { type: "updated" },
  };
}

/** Which phase the UI shows, given the server clock. */
export type Phase = "upcoming" | "live" | "closing" | "pending_payment" | "ended" | "cancelled";

export function phaseOf(state: Pick<AuctionState, "status" | "starts_at" | "ends_at">, serverNow: number): Phase {
  switch (state.status) {
    case "cancelled":
      return "cancelled";
    case "pending_winner_payment":
      return "pending_payment";
    case "ended":
    case "awarded":
      return "ended";
    default:
      if (serverNow < Date.parse(state.starts_at)) return "upcoming";
      // The server closes the auction; until its event arrives the UI says "closing".
      return serverNow < Date.parse(state.ends_at) ? "live" : "closing";
  }
}

/** Quick increments: +1×, +2×, +5× the minimum increment over the minimum next bid. */
export function quickAmounts(minimumNext: string, increment: string): string[] {
  const min = Number(minimumNext);
  const step = Number(increment);
  return [0, 1, 4].map((k) => (min + k * step).toFixed(2));
}

/** Parses a typed amount ("1,250.5" or Arabic-Indic digits) into a 2-decimal string. */
export function normalizeAmount(raw: string): string | null {
  const latin = raw
    .trim()
    .replace(/[٠-٩]/g, (d) => String(d.charCodeAt(0) - 0x0660))
    .replace(/[۰-۹]/g, (d) => String(d.charCodeAt(0) - 0x06f0))
    .replace(/[,٬\s]/g, "")
    .replace(/٫/g, ".");
  if (!/^\d+(\.\d{1,2})?$/.test(latin)) return null;
  const value = Number(latin);
  return value > 0 ? value.toFixed(2) : null;
}
