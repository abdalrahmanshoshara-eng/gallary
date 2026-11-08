import { apiFetch } from "@/lib/api/client";
import type { Schema } from "@/lib/api/types";

export type AdminPage = Schema<"AdminPage">;
export type PageVersion = Schema<"PageVersion">;
export type AdminFaq = Schema<"AdminFaq">;
export type AdminBanner = Schema<"AdminBanner">;
export type AdminFeatured = Schema<"AdminFeatured">;
export type Direction = "up" | "down";

export const pagesKey = ["admin", "content", "pages"] as const;
export const pageKey = (slug: string) => ["admin", "content", "page", slug] as const;
export const faqKey = ["admin", "content", "faq"] as const;
export const bannersKey = ["admin", "content", "banners"] as const;
export const featuredKey = ["admin", "content", "featured"] as const;

export const listPages = () => apiFetch<AdminPage[]>("/admin/content/pages");
export const getPage = (slug: string) => apiFetch<AdminPage>(`/admin/content/pages/${slug}`);
export const saveDraft = (slug: string, title: string, body: string) =>
  apiFetch<AdminPage>(`/admin/content/pages/${slug}`, { method: "PUT", body: { title, body } });
export const publishPage = (slug: string) => apiFetch<AdminPage>(`/admin/content/pages/${slug}/publish`, { method: "POST" });
export const getVersion = (slug: string, number: number) => apiFetch<PageVersion>(`/admin/content/pages/${slug}/versions/${number}`);

export const listFaq = () => apiFetch<AdminFaq[]>("/admin/content/faq");
export const createFaq = (body: { question: string; answer: string }) => apiFetch<AdminFaq[]>("/admin/content/faq", { method: "POST", body });
export const updateFaq = (id: string, body: Partial<{ question: string; answer: string; is_active: boolean }>) =>
  apiFetch<AdminFaq[]>(`/admin/content/faq/${id}`, { method: "PATCH", body });
export const deleteFaq = (id: string) => apiFetch<AdminFaq[]>(`/admin/content/faq/${id}`, { method: "DELETE" });
export const moveFaq = (id: string, direction: Direction) =>
  apiFetch<AdminFaq[]>(`/admin/content/faq/${id}/move`, { method: "POST", body: { direction } });

export const listBanners = () => apiFetch<AdminBanner[]>("/admin/content/banners");
export const createBanner = (form: FormData) => apiFetch<AdminBanner[]>("/admin/content/banners", { method: "POST", body: form });
export const updateBanner = (id: string, form: FormData) => apiFetch<AdminBanner[]>(`/admin/content/banners/${id}`, { method: "PATCH", body: form });
export const deleteBanner = (id: string) => apiFetch<AdminBanner[]>(`/admin/content/banners/${id}`, { method: "DELETE" });
export const moveBanner = (id: string, direction: Direction) =>
  apiFetch<AdminBanner[]>(`/admin/content/banners/${id}/move`, { method: "POST", body: { direction } });

export const listFeatured = () => apiFetch<AdminFeatured[]>("/admin/content/featured");
export const addFeatured = (artwork: string) => apiFetch<AdminFeatured[]>("/admin/content/featured", { method: "POST", body: { artwork } });
export const removeFeatured = (artwork: string) => apiFetch<AdminFeatured[]>(`/admin/content/featured/${artwork}`, { method: "DELETE" });
export const moveFeatured = (artwork: string, direction: Direction) =>
  apiFetch<AdminFeatured[]>(`/admin/content/featured/${artwork}/move`, { method: "POST", body: { direction } });
