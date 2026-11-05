import { apiFetch } from "@/lib/api/client";
import type { Schema } from "@/lib/api/types";

export type AdminAuction = Schema<"AdminAuction">;
export type AdminAuctionCard = Schema<"AuctionCard">;
export type EligibleArtwork = Schema<"EligibleArtwork">;
export type AdminAuctionRequest = Schema<"AdminAuctionRequest">;
export type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] };

const qs = (params: Record<string, string | number>) =>
  new URLSearchParams(Object.entries(params).filter(([, v]) => v !== "" && v !== "all").map(([k, v]) => [k, String(v)])).toString();

export const adminAuctionsKey = (params: Record<string, string | number>) => ["admin", "auctions", params] as const;
export const adminAuctionKey = (id: string) => ["admin", "auction", id] as const;
export const adminRequestsKey = (params: Record<string, string | number>) => ["admin", "auction-requests", params] as const;
export const adminRequestKey = (id: string) => ["admin", "auction-request", id] as const;

export const listAdminAuctions = (params: Record<string, string | number>) =>
  apiFetch<Page<AdminAuctionCard>>(`/admin/auctions?${qs(params)}`);
export const getAdminAuction = (id: string) => apiFetch<AdminAuction>(`/admin/auctions/${id}`);
export const listEligibleArtworks = (search: string) =>
  apiFetch<Page<EligibleArtwork>>(`/admin/auctions/eligible-artworks?${qs({ search })}`);
export const createAuction = (body: Record<string, unknown>) =>
  apiFetch<AdminAuction>("/admin/auctions", { method: "POST", body });
export const updateAuction = (id: string, body: Record<string, unknown>) =>
  apiFetch<AdminAuction>(`/admin/auctions/${id}`, { method: "PATCH", body });
export const scheduleAuction = (id: string) => apiFetch<AdminAuction>(`/admin/auctions/${id}/schedule`, { method: "POST" });
export const cancelAuction = (id: string, reason: string) =>
  apiFetch<AdminAuction>(`/admin/auctions/${id}/cancel`, { method: "POST", body: { reason } });

export const listAdminRequests = (params: Record<string, string | number>) =>
  apiFetch<Page<AdminAuctionRequest>>(`/admin/auction-requests?${qs(params)}`);
export const getAdminRequest = (id: string) => apiFetch<AdminAuctionRequest>(`/admin/auction-requests/${id}`);
export const transitionRequest = (id: string, to: string, message: string) =>
  apiFetch<AdminAuctionRequest>(`/admin/auction-requests/${id}/transition`, { method: "POST", body: { to, message } });
export const addRequestNote = (id: string, body: string, visibility: "internal" | "customer") =>
  apiFetch<AdminAuctionRequest>(`/admin/auction-requests/${id}/notes`, { method: "POST", body: { body, visibility } });
export const setRequestCommission = (id: string, rate: string, note: string) =>
  apiFetch<AdminAuctionRequest>(`/admin/auction-requests/${id}/commission`, { method: "POST", body: { rate, note } });
export const createRequestArtwork = (id: string, category: string) =>
  apiFetch<AdminAuctionRequest>(`/admin/auction-requests/${id}/artwork`, { method: "POST", body: { category } });
