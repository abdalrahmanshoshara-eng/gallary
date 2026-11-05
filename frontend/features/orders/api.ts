import { apiFetch } from "@/lib/api/client";
import type { Schema } from "@/lib/api/types";

export type Order = Schema<"CustomerOrder">;
export type OrderSummary = Schema<"OrderSummary">;
export type Policy = Schema<"Policy">;
export type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] };

export const orderKey = (number: string) => ["orders", number] as const;
export const ordersKey = ["orders", "mine"] as const;
export const policyKey = ["orders", "policy"] as const;

export const getPolicy = () => apiFetch<Policy>("/orders/policy");
export const checkout = (body: Record<string, unknown>, idempotencyKey: string) =>
  apiFetch<Order>("/orders/checkout", { method: "POST", body, idempotencyKey });
export const listOrders = () => apiFetch<Page<OrderSummary>>("/orders?page_size=50");
export const getOrder = (number: string) => apiFetch<Order>(`/orders/${encodeURIComponent(number)}`);
export const cancelOrder = (number: string, reason: string) =>
  apiFetch<Order>(`/orders/${encodeURIComponent(number)}/cancel`, { method: "POST", body: { reason } });
