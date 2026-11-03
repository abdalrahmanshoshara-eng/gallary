"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";

import type { CurrentUser } from "./types";

export const currentUserKey = ["auth", "me"] as const;

export async function fetchCurrentUser(): Promise<CurrentUser | null> {
  try {
    return await apiFetch<CurrentUser>("/auth/me");
  } catch (error) {
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) return null;
    throw error;
  }
}

/** Client-side session state; public pages stay static and cacheable (no cookies at render). */
export function useCurrentUser() {
  return useQuery({ queryKey: currentUserKey, queryFn: fetchCurrentUser, staleTime: 60_000 });
}
