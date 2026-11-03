/**
 * Server-side API client for React Server Components (reads only).
 * Calls Django over the internal network and forwards the visitor's cookies so that
 * Django — not Next.js — decides what the visitor may see (ARCHITECTURE §4.4).
 */
import "server-only";

import { cookies, headers } from "next/headers";

import { ApiError, NETWORK_ERROR_MESSAGE, toApiError } from "./errors";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://localhost:8000";

export async function serverApiGet<T>(path: string, init: { revalidate?: number | false } = {}): Promise<T> {
  const [cookieStore, incoming] = await Promise.all([cookies(), headers()]);
  const forwarded = new Headers({ Accept: "application/json" });
  const cookieHeader = cookieStore.toString();
  if (cookieHeader) forwarded.set("Cookie", cookieHeader);
  for (const name of ["x-request-id", "x-forwarded-proto", "x-forwarded-host", "host"]) {
    const value = incoming.get(name);
    if (value) forwarded.set(name, value);
  }

  let response: Response;
  try {
    response = await fetch(`${INTERNAL_API_URL}/api/v1${path}`, {
      headers: forwarded,
      // Personalised responses must never be cached across visitors.
      ...(cookieHeader ? { cache: "no-store" as const } : { next: { revalidate: init.revalidate ?? 60 } }),
    });
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", NETWORK_ERROR_MESSAGE);
  }
  if (!response.ok) throw await toApiError(response);
  return (await response.json()) as T;
}
