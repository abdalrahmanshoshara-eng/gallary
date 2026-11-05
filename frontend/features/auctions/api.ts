"use client";

import { apiFetch } from "@/lib/api/client";
import type { Schema } from "@/lib/api/types";

import type { AuctionState } from "./live";

export type AuctionCard = Schema<"AuctionCard">;
export type AuctionDetail = Schema<"AuctionDetail">;
export type BidResult = Schema<"BidResult">;
export type MyBidAuction = Schema<"MyBidAuction">;

export const auctionStateKey = (id: string) => ["auctions", id, "state"] as const;
export const myBidsKey = ["auctions", "mine"] as const;

export const getAuctionState = (id: string) => apiFetch<AuctionState>(`/auctions/${id}/state`);

export const placeBid = (vars: { id: string; amount: string; key: string }) =>
  apiFetch<BidResult>(`/auctions/${vars.id}/bids`, { method: "POST", body: { amount: vars.amount }, idempotencyKey: vars.key });

export const listMyBids = () => apiFetch<MyBidAuction[]>("/me/bids");

/** Reasons the server gives when it refuses a bid (BID_REJECTED details.reason). */
export type BidRejection = "too_low" | "already_highest" | "not_started" | "ended" | "not_open";
