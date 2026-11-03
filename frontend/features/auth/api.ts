import { apiFetch } from "@/lib/api/client";
import type { Schema } from "@/lib/api/types";

export type OtpRequested = Schema<"OtpRequested">;
export type LoginResult = Schema<"LoginResult">;

export const requestOtp = (phone: string) =>
  apiFetch<OtpRequested>("/auth/otp/request", { method: "POST", body: { phone } });

export const verifyOtp = (phone: string, code: string) =>
  apiFetch<LoginResult>("/auth/otp/verify", { method: "POST", body: { phone, code } });

export const logout = () => apiFetch<void>("/auth/logout", { method: "POST" });
