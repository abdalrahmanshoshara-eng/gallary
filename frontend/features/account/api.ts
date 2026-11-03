import { apiFetch } from "@/lib/api/client";
import type { Schema } from "@/lib/api/types";
import type { CurrentUser } from "@/lib/auth/types";

export type Session = Schema<"Session">;

export const sessionsKey = ["auth", "sessions"] as const;

export const updateProfile = (body: Schema<"PatchedProfileUpdateRequest">) =>
  apiFetch<CurrentUser>("/auth/me", { method: "PATCH", body });
export const listSessions = () => apiFetch<Session[]>("/auth/sessions");
export const endSession = (id: string) => apiFetch<void>(`/auth/sessions/${id}`, { method: "DELETE" });
export const endOtherSessions = () =>
  apiFetch<Schema<"RevokedCount">>("/auth/sessions/revoke-others", { method: "POST" });
