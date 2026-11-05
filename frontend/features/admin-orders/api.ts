import { apiFetch } from "@/lib/api/client";
import type { Schema } from "@/lib/api/types";

export type AdminOrder = Schema<"AdminOrder">;
export type AdminOrderListItem = Schema<"AdminOrderList">;
export type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] };

export const adminOrdersKey = (params: Record<string, string | number>) => ["admin", "orders", params] as const;
export const adminOrderKey = (number: string) => ["admin", "order", number] as const;

const base = (number: string) => `/admin/orders/${encodeURIComponent(number)}`;
const qs = (params: Record<string, string | number>) =>
  new URLSearchParams(Object.entries(params).filter(([, v]) => v !== "" && v !== "all").map(([k, v]) => [k, String(v)])).toString();

export const listAdminOrders = (params: Record<string, string | number>) =>
  apiFetch<Page<AdminOrderListItem>>(`/admin/orders?${qs(params)}`);
export const getAdminOrder = (number: string) => apiFetch<AdminOrder>(base(number));
export const saveNotes = (number: string, internal_notes: string) =>
  apiFetch<AdminOrder>(base(number), { method: "PATCH", body: { internal_notes } });
export const recordPayment = (number: string, body: Record<string, unknown>, idempotencyKey: string) =>
  apiFetch<AdminOrder>(`${base(number)}/payments`, { method: "POST", body, idempotencyKey });
export const confirmPayment = (number: string, id: string) =>
  apiFetch<AdminOrder>(`${base(number)}/payments/${id}/confirm`, { method: "POST" });
export const voidPayment = (number: string, id: string, reason: string) =>
  apiFetch<AdminOrder>(`${base(number)}/payments/${id}/void`, { method: "POST", body: { reason } });
export const removeItem = (number: string, id: string, reason: string) =>
  apiFetch<AdminOrder>(`${base(number)}/items/${id}/remove`, { method: "POST", body: { reason } });
export const customDeposit = (number: string, amount: string, reason: string) =>
  apiFetch<AdminOrder>(`${base(number)}/deposit`, { method: "POST", body: { amount, reason } });
export const cancelOrder = (number: string, kind: "platform" | "customer", reason: string) =>
  apiFetch<AdminOrder>(`${base(number)}/cancel`, { method: "POST", body: { kind, reason } });
export const saveDelivery = (number: string, body: Record<string, unknown>) =>
  apiFetch<AdminOrder>(`${base(number)}/delivery`, { method: "PUT", body });
export const completeOrder = (number: string) => apiFetch<AdminOrder>(`${base(number)}/complete`, { method: "POST" });
