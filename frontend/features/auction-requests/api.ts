"use client";

import { apiFetch } from "@/lib/api/client";
import type { Schema } from "@/lib/api/types";

export type AuctionRequest = Schema<"AuctionRequest">;
export type RequestStatus = AuctionRequest["status"];

export const requestsKey = ["auction-requests", "mine"] as const;
export const requestKey = (id: string) => ["auction-requests", "mine", id] as const;

export const listRequests = () => apiFetch<AuctionRequest[]>("/auction-requests");
export const getRequest = (id: string) => apiFetch<AuctionRequest>(`/auction-requests/${id}`);

export type RequestFields = {
  work_title: string;
  work_description: string;
  artist_name: string;
  artist_info: string;
  category_hint: string;
  dimensions_text: string;
  year_text: string;
  expected_price: string;
  customer_notes: string;
};

function toForm(fields: Partial<RequestFields>, images: File[]): FormData {
  const form = new FormData();
  for (const [key, value] of Object.entries(fields)) {
    // An empty optional price is omitted (null); other optional texts may be cleared.
    if (key === "expected_price" && !value) continue;
    form.append(key, value ?? "");
  }
  for (const image of images) form.append("images", image);
  return form;
}

export const submitRequest = (vars: { fields: RequestFields; images: File[] }) =>
  apiFetch<AuctionRequest>("/auction-requests", { method: "POST", body: toForm(vars.fields, vars.images) });

export const updateRequest = (vars: { id: string; fields: Partial<RequestFields>; images: File[] }) =>
  apiFetch<AuctionRequest>(`/auction-requests/${vars.id}`, { method: "PATCH", body: toForm(vars.fields, vars.images) });

export const withdrawRequest = (id: string) => apiFetch<AuctionRequest>(`/auction-requests/${id}/withdraw`, { method: "POST" });

/** Statuses in which the customer is waiting on the platform (or on themselves). */
export const ACTIVE_STATUSES: ReadonlySet<string> = new Set(["submitted", "under_review", "needs_more_info", "negotiation"]);
