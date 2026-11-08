import { apiFetch } from "@/lib/api/client";
import type { Schema } from "@/lib/api/types";

export type AppNotification = Schema<"Notification">;
export type NotificationPreferences = Schema<"Preferences">;
export type Page<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export const PAGE_SIZE = 20;
export const notificationsKey = ["notifications"] as const;
export const unreadCountKey = ["notifications", "unread-count"] as const;
export const listKey = (filter: "all" | "unread") =>
  ["notifications", "list", filter] as const;
export const preferencesKey = ["notifications", "preferences"] as const;

export const getUnreadCount = () =>
  apiFetch<{ unread: number }>("/notifications/unread-count");
export const listNotifications = (filter: "all" | "unread", page: number) =>
  apiFetch<Page<AppNotification>>(
    `/notifications?page=${page}&page_size=${PAGE_SIZE}${filter === "unread" ? "&unread=1" : ""}`,
  );
export const markRead = (id: string) =>
  apiFetch<AppNotification>(`/notifications/${id}/read`, { method: "POST" });
export const markAllRead = () =>
  apiFetch<{ updated: number; unread: number }>("/notifications/read-all", {
    method: "POST",
  });
export const getPreferences = () =>
  apiFetch<NotificationPreferences>("/notifications/preferences");
export const updatePreferences = (email_enabled: boolean) =>
  apiFetch<NotificationPreferences>("/notifications/preferences", {
    method: "PATCH",
    body: { email_enabled },
  });

/** Page number from DRF's absolute `next` URL. */
export function nextPage(next: string | null): number | undefined {
  if (!next) return undefined;
  const page = new URL(next, "http://x").searchParams.get("page");
  return page ? Number(page) : undefined;
}
