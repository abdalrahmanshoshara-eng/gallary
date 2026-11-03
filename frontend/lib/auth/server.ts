/**
 * Current user for Server Components. Django decides — Next.js only forwards the cookie.
 * Cached per request so the header and the page share one API call.
 */
import "server-only";

import { cache } from "react";

import { ApiError } from "@/lib/api/errors";
import { serverApiGet } from "@/lib/api/server";

import type { CurrentUser } from "./types";

export const getCurrentUser = cache(async (): Promise<CurrentUser | null> => {
  try {
    return await serverApiGet<CurrentUser>("/auth/me", { revalidate: false });
  } catch (error) {
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) return null;
    throw error;
  }
});
