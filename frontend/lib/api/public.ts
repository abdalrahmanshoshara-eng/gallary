/**
 * Server-side reads of PUBLIC data for catalogue pages. Unlike serverApiGet it never
 * forwards the visitor's cookies, so responses are identical for everyone and can be
 * cached (ISR) — public pages stay fast and cheap regardless of who is signed in.
 */
import "server-only";

import { ApiError, NETWORK_ERROR_MESSAGE, toApiError } from "./errors";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://localhost:8000";

export type QueryParams = Record<string, string | number | string[] | undefined | null>;

export function toQuery(params: QueryParams = {}): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    for (const item of Array.isArray(value) ? value : [value]) {
      if (item !== undefined && item !== null && item !== "") query.append(key, String(item));
    }
  }
  const text = query.toString();
  return text ? `?${text}` : "";
}

export async function publicApiGet<T>(path: string, params?: QueryParams, revalidate = 60): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${INTERNAL_API_URL}/api/v1${path}${toQuery(params)}`, {
      headers: { Accept: "application/json" },
      next: { revalidate },
    });
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", NETWORK_ERROR_MESSAGE);
  }
  if (!response.ok) throw await toApiError(response);
  return (await response.json()) as T;
}

/** Same as publicApiGet but resolves to null on 404 (for detail pages → notFound()). */
export async function publicApiGetOrNull<T>(path: string, revalidate = 60): Promise<T | null> {
  try {
    return await publicApiGet<T>(path, undefined, revalidate);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}
