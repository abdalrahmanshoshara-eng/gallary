import type { Schema } from "@/lib/api/types";

export type CurrentUser = Schema<"Me">;

export const ROLES = ["content_staff", "operations_staff", "auction_manager", "super_admin"] as const;
export type RoleName = (typeof ROLES)[number];

export function hasRole(user: CurrentUser | null, role: RoleName): boolean {
  return Boolean(user?.roles.includes(role));
}

export function isCatalogEditor(user: CurrentUser | null): boolean {
  return hasRole(user, "content_staff") || hasRole(user, "super_admin");
}

export function isOrdersStaff(user: CurrentUser | null): boolean {
  return hasRole(user, "operations_staff") || hasRole(user, "super_admin");
}
