import { apiFetch } from "@/lib/api/client";
import type { Schema } from "@/lib/api/types";

export type AdminArtist = Schema<"AdminArtist">;
export type AdminArtwork = Schema<"AdminArtwork">;
export type AdminArtworkListItem = Schema<"AdminArtworkList">;
export type AdminArtworkImage = Schema<"AdminArtworkImage">;
export type AdminCategory = Schema<"AdminCategory">;
export type AdminTerm = Schema<"AdminMaterial">;
export type TermKind = "categories" | "materials" | "techniques" | "tags";
export type Paginated<T> = { count: number; next: string | null; previous: string | null; results: T[] };

const qs = (params: Record<string, string | number | undefined>) => {
  const q = new URLSearchParams(
    Object.entries(params)
      .filter(([, v]) => v !== undefined && v !== "")
      .map(([k, v]) => [k, String(v)]),
  ).toString();
  return q ? `?${q}` : "";
};

// --- classifications -------------------------------------------------------------------
export const termsKey = (kind: TermKind) => ["admin", "catalog", kind] as const;
export const listTerms = <T = AdminTerm>(kind: TermKind) => apiFetch<T[]>(`/admin/catalog/${kind}`);
export const createTerm = (kind: TermKind, body: Record<string, unknown>) =>
  apiFetch<AdminTerm>(`/admin/catalog/${kind}`, { method: "POST", body });
export const updateTerm = (kind: TermKind, id: number, body: Record<string, unknown>) =>
  apiFetch<AdminTerm>(`/admin/catalog/${kind}/${id}`, { method: "PATCH", body });
export const deleteTerm = (kind: TermKind, id: number) =>
  apiFetch<void>(`/admin/catalog/${kind}/${id}`, { method: "DELETE" });

// --- artists -----------------------------------------------------------------------------
export const artistsKey = (params: Record<string, string | number | undefined> = {}) =>
  ["admin", "artists", params] as const;
export const artistKey = (id: string) => ["admin", "artist", id] as const;
export const listArtists = (params: Record<string, string | number | undefined> = {}) =>
  apiFetch<Paginated<AdminArtist>>(`/admin/artists${qs(params)}`);
export const getArtist = (id: string) => apiFetch<AdminArtist>(`/admin/artists/${id}`);
export const createArtist = (body: Record<string, unknown>) =>
  apiFetch<AdminArtist>("/admin/artists", { method: "POST", body });
export const updateArtist = (id: string, body: Record<string, unknown>) =>
  apiFetch<AdminArtist>(`/admin/artists/${id}`, { method: "PATCH", body });
export const deleteArtist = (id: string) => apiFetch<void>(`/admin/artists/${id}`, { method: "DELETE" });
export function uploadArtistPhoto(id: string, file: File) {
  const form = new FormData();
  form.append("file", file);
  return apiFetch<AdminArtist>(`/admin/artists/${id}/photo`, { method: "POST", body: form });
}
export const removeArtistPhoto = (id: string) =>
  apiFetch<AdminArtist>(`/admin/artists/${id}/photo`, { method: "DELETE" });

// --- artworks ------------------------------------------------------------------------------
export const artworksKey = (params: Record<string, string | number | undefined> = {}) =>
  ["admin", "artworks", params] as const;
export const artworkKey = (id: string) => ["admin", "artwork", id] as const;
export const listArtworks = (params: Record<string, string | number | undefined> = {}) =>
  apiFetch<Paginated<AdminArtworkListItem>>(`/admin/artworks${qs(params)}`);
export const getArtwork = (id: string) => apiFetch<AdminArtwork>(`/admin/artworks/${id}`);
export const createArtwork = (body: Record<string, unknown>) =>
  apiFetch<AdminArtwork>("/admin/artworks", { method: "POST", body });
export const updateArtwork = (id: string, body: Record<string, unknown>) =>
  apiFetch<AdminArtwork>(`/admin/artworks/${id}`, { method: "PATCH", body });
export const deleteArtwork = (id: string) => apiFetch<void>(`/admin/artworks/${id}`, { method: "DELETE" });
export const artworkAction = (
  id: string,
  action: "publish" | "hide" | "archive" | "unarchive",
  body?: Record<string, unknown>,
) => apiFetch<AdminArtwork>(`/admin/artworks/${id}/${action}`, { method: "POST", body: body ?? {} });

export function uploadArtworkImage(id: string, file: File, altText = "") {
  const form = new FormData();
  form.append("file", file);
  form.append("alt_text", altText);
  return apiFetch<AdminArtworkImage>(`/admin/artworks/${id}/images`, { method: "POST", body: form });
}
export const reorderImages = (id: string, ids: string[]) =>
  apiFetch<AdminArtwork>(`/admin/artworks/${id}/images/order`, { method: "PUT", body: { ids } });
export const updateImage = (id: string, imageId: string, body: { alt_text?: string; is_primary?: boolean }) =>
  apiFetch<AdminArtwork>(`/admin/artworks/${id}/images/${imageId}`, { method: "PATCH", body });
export const deleteImage = (id: string, imageId: string) =>
  apiFetch<AdminArtwork>(`/admin/artworks/${id}/images/${imageId}`, { method: "DELETE" });

// --- listings & settings ---------------------------------------------------------------------
export type AdminListing = Schema<"AdminListing">;
export type SiteSettings = Schema<"SiteSetting">;
export const listingsKey = (artworkId: string) => ["admin", "artwork", artworkId, "listings"] as const;
export const listListings = (artworkId: string) => apiFetch<AdminListing[]>(`/admin/artworks/${artworkId}/listings`);
export const createListing = (artworkId: string, body: Record<string, unknown>) =>
  apiFetch<AdminListing>(`/admin/artworks/${artworkId}/listings`, { method: "POST", body });
export const updateListing = (id: string, body: Record<string, unknown>) =>
  apiFetch<AdminListing>(`/admin/listings/${id}`, { method: "PATCH", body });
export const deleteListing = (id: string) => apiFetch<void>(`/admin/listings/${id}`, { method: "DELETE" });
export const priceListing = (id: string, body: Record<string, unknown>) =>
  apiFetch<AdminListing>(`/admin/listings/${id}/pricing`, { method: "POST", body });
export const listingAction = (id: string, action: "activate" | "withdraw", body?: Record<string, unknown>) =>
  apiFetch<AdminListing>(`/admin/listings/${id}/${action}`, { method: "POST", body: body ?? {} });
export const settingsKey = ["admin", "settings"] as const;
export const getSettings = () => apiFetch<SiteSettings>("/admin/settings");
export const updateSettings = (body: Record<string, unknown>) =>
  apiFetch<SiteSettings>("/admin/settings", { method: "PATCH", body });
