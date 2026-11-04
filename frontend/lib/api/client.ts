/**
 * Browser API client. Same-origin requests to /api/v1 carry the session cookie
 * automatically; unsafe methods add the CSRF header read from the CSRF cookie (ADR-06).
 * Mutations always go straight from the browser to Django — never through Next.js.
 */
import { ApiError, NETWORK_ERROR_MESSAGE, toApiError } from "./errors";

export const API_BASE = "/api/v1";
const CSRF_COOKIE = process.env.NEXT_PUBLIC_CSRF_COOKIE_NAME ?? "__Host-csrf";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

export function readCookie(name: string, cookieString: string = typeof document === "undefined" ? "" : document.cookie) {
  for (const part of cookieString.split(";")) {
    const [rawKey, ...rest] = part.trim().split("=");
    if (rawKey === name) return decodeURIComponent(rest.join("="));
  }
  return null;
}

export type ApiRequestOptions = Omit<RequestInit, "body"> & {
  /** JSON body, or FormData for file uploads (sent as multipart, browser sets the boundary). */
  body?: unknown;
  /** Sent as Idempotency-Key for financial/sensitive POSTs (ARCHITECTURE §7.4). */
  idempotencyKey?: string;
};

let csrfBootstrap: Promise<void> | null = null;

/** Make sure the CSRF cookie exists (first unsafe request of a visit). */
async function ensureCsrfCookie(): Promise<string | null> {
  const existing = readCookie(CSRF_COOKIE);
  if (existing) return existing;
  csrfBootstrap ??= fetch(`${API_BASE}/auth/csrf`, { credentials: "same-origin" })
    .then(() => undefined)
    .finally(() => {
      csrfBootstrap = null;
    });
  await csrfBootstrap;
  return readCookie(CSRF_COOKIE);
}

export async function apiFetch<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const { body, idempotencyKey, headers: extraHeaders, ...init } = options;
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(extraHeaders);
  headers.set("Accept", "application/json");
  const isForm = typeof FormData !== "undefined" && body instanceof FormData;
  if (body !== undefined && !isForm) headers.set("Content-Type", "application/json");
  if (!SAFE_METHODS.has(method)) {
    let csrf: string | null = null;
    try {
      csrf = await ensureCsrfCookie();
    } catch {
      throw new ApiError(0, "NETWORK_ERROR", NETWORK_ERROR_MESSAGE);
    }
    if (csrf) headers.set("X-CSRFToken", csrf);
  }
  if (idempotencyKey) headers.set("Idempotency-Key", idempotencyKey);

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      method,
      headers,
      credentials: "same-origin",
      body: body === undefined ? undefined : isForm ? (body as FormData) : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", NETWORK_ERROR_MESSAGE);
  }

  if (!response.ok) throw await toApiError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
