import { apiFetch } from "@/lib/api/client";
import type { Schema } from "@/lib/api/types";

export type Settlement = Schema<"Settlement">;
export type SettlementSummary = Schema<"SettlementSummary">;
export type PayeeDue = Schema<"PayeeDue">;
export type ArtistAgreements = Schema<"ArtistAgreements">;
export type Dashboard = Schema<"Dashboard">;
export type AuditEntry = Schema<"AuditEntry">;
export type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] };

const qs = (params: Record<string, string | number>) =>
  new URLSearchParams(Object.entries(params).filter(([, v]) => v !== "" && v !== "all").map(([k, v]) => [k, String(v)])).toString();

// --- settlements ---------------------------------------------------------------------------------
export const settlementsKey = ["admin", "settlements"] as const;
export const listSettlements = (params: Record<string, string | number>) =>
  apiFetch<Page<Settlement>>(`/admin/settlements?${qs(params)}`);
export const getSettlementSummary = () => apiFetch<SettlementSummary>("/admin/settlements/summary");
export const listPayeesDue = () => apiFetch<PayeeDue[]>("/admin/settlements/payees");
export const paySettlements = (body: { settlements: string[]; reference: string; paid_at: string; notes: string }, idempotencyKey: string) =>
  apiFetch<Settlement[]>("/admin/settlements/pay", { method: "POST", body, idempotencyKey });
export const holdSettlement = (id: string, reason: string) =>
  apiFetch<Settlement>(`/admin/settlements/${id}/hold`, { method: "POST", body: { reason } });
export const releaseSettlement = (id: string) => apiFetch<Settlement>(`/admin/settlements/${id}/release`, { method: "POST" });
export const cancelSettlement = (id: string, reason: string) =>
  apiFetch<Settlement>(`/admin/settlements/${id}/cancel`, { method: "POST", body: { reason } });

// --- artist agreements -----------------------------------------------------------------------------
export const agreementsKey = (artistId: string) => ["admin", "artist", artistId, "agreements"] as const;
export const getAgreements = (artistId: string) => apiFetch<ArtistAgreements>(`/admin/artists/${artistId}/agreements`);
export const createAgreement = (artistId: string, commission_rate: string, notes: string) =>
  apiFetch<ArtistAgreements>(`/admin/artists/${artistId}/agreements`, { method: "POST", body: { commission_rate, notes } });
export const endAgreement = (artistId: string) =>
  apiFetch<ArtistAgreements>(`/admin/artists/${artistId}/agreements/end`, { method: "POST" });

// --- dashboard and audit ------------------------------------------------------------------------------
export const dashboardKey = (period: string) => ["admin", "dashboard", period] as const;
export const getDashboard = (period: string) => apiFetch<Dashboard>(`/admin/dashboard?period=${period}`);
export const auditKey = (params: Record<string, string | number>) => ["admin", "audit", params] as const;
export const listAudit = (params: Record<string, string | number>) => apiFetch<Page<AuditEntry>>(`/admin/audit?${qs(params)}`);
export const getAuditFacets = () => apiFetch<{ entity_types: string[] }>("/admin/audit/facets");

export const newKey = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`.replace(".", "");

/** Sums decimal strings exactly (in cents) for display totals. */
export function sumAmounts(values: string[]): string {
  const cents = values.reduce((acc, v) => acc + Math.round(Number(v) * 100), 0);
  return (cents / 100).toFixed(2);
}
