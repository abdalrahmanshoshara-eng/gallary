import { apiFetch } from "@/lib/api/client";
import type { Schema } from "@/lib/api/types";
import type { CurrentUser } from "@/lib/auth/types";

export type RegisterInput = Schema<"RegisterInputRequest">;

export const login = (phone: string, password: string) =>
  apiFetch<CurrentUser>("/auth/login", { method: "POST", body: { phone, password } });

export const register = (body: RegisterInput) => apiFetch<CurrentUser>("/auth/register", { method: "POST", body });

export const changePassword = (current_password: string, new_password: string) =>
  apiFetch<{ revoked: number }>("/auth/password", { method: "POST", body: { current_password, new_password } });

export const logout = () => apiFetch<void>("/auth/logout", { method: "POST" });
