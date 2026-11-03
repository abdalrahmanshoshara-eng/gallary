import { afterEach, describe, expect, it, vi } from "vitest";

import { apiFetch, readCookie } from "./client";
import { ApiError } from "./errors";

function jsonResponse(status: number, body: unknown, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", ...headers } });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

// jsdom rightly refuses to set `__Host-` cookies over http, so stub the getter.
function withCookies(value: string) {
  vi.spyOn(document, "cookie", "get").mockReturnValue(value);
}

describe("readCookie", () => {
  it("finds a cookie and decodes it", () => {
    expect(readCookie("b", "a=1; b=x%3Dy; c=3")).toBe("x=y");
    expect(readCookie("missing", "a=1")).toBeNull();
  });
});

describe("apiFetch", () => {
  it("sends CSRF and idempotency headers on unsafe methods only", async () => {
    withCookies("other=1; __Host-csrf=tok123");
    const fetchMock = vi.fn().mockImplementation(async () => jsonResponse(200, { ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("/things", { method: "POST", body: { a: 1 }, idempotencyKey: "k-1" });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = new Headers(init.headers);
    expect(url).toBe("/api/v1/things");
    expect(init.credentials).toBe("same-origin");
    expect(headers.get("X-CSRFToken")).toBe("tok123");
    expect(headers.get("Idempotency-Key")).toBe("k-1");
    expect(init.body).toBe('{"a":1}');

    await apiFetch("/things");
    const getHeaders = new Headers((fetchMock.mock.calls[1] as [string, RequestInit])[1].headers);
    expect(getHeaders.has("X-CSRFToken")).toBe(false);
  });

  it("turns the backend error envelope into an ApiError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(400, {
          error: { code: "VALIDATION_ERROR", message: "البيانات غير صالحة", details: { amount: ["مطلوب"] }, request_id: "r1" },
        }),
      ),
    );
    const error = await apiFetch("/x", { method: "POST", body: {} }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    const apiError = error as ApiError;
    expect(apiError.status).toBe(400);
    expect(apiError.code).toBe("VALIDATION_ERROR");
    expect(apiError.requestId).toBe("r1");
    expect(apiError.fieldErrors).toEqual({ amount: ["مطلوب"] });
  });

  it("reports non-JSON failures and network failures with safe messages", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("<html>bad gateway</html>", { status: 502 })));
    await expect(apiFetch("/x")).rejects.toMatchObject({ status: 502, code: "HTTP_ERROR" });

    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(apiFetch("/x")).rejects.toMatchObject({ status: 0, code: "NETWORK_ERROR" });
  });
});
