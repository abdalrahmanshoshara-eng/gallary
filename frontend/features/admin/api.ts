import { apiFetch } from "@/lib/api/client";
import type { Schema } from "@/lib/api/types";
import type { RoleName } from "@/lib/auth/types";

export type AdminUser = Schema<"AdminUser">;
export type UserPage = Schema<"PaginatedAdminUserList">;

export const staffKey = ["admin", "staff"] as const;
export const usersKey = (params: Record<string, string>) => ["admin", "users", params] as const;

export const listStaff = () => apiFetch<AdminUser[]>("/admin/staff");
export const createStaff = (body: { phone: string; display_name: string; roles: RoleName[]; password: string }) =>
  apiFetch<AdminUser>("/admin/staff", { method: "POST", body });
export const updateStaff = (id: string, body: { display_name?: string; roles?: RoleName[] }) =>
  apiFetch<AdminUser>(`/admin/staff/${id}`, { method: "PATCH", body });
export const revokeStaff = (id: string) => apiFetch<AdminUser>(`/admin/staff/${id}`, { method: "DELETE" });

export function listUsers(params: Record<string, string>) {
  const query = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== ""));
  return apiFetch<UserPage>(`/admin/users?${query.toString()}`);
}
export const setActive = (id: string, active: boolean, reason = "") =>
  apiFetch<AdminUser>(`/admin/users/${id}/${active ? "activate" : "deactivate"}`, {
    method: "POST",
    body: { reason },
  });
export const revokeUserSessions = (id: string) =>
  apiFetch<Schema<"RevokedCount">>(`/admin/users/${id}/revoke-sessions`, { method: "POST" });
export const setUserPassword = (id: string, password: string) =>
  apiFetch<void>(`/admin/users/${id}/set-password`, { method: "POST", body: { password } });
