import { z } from "zod";

/** Mirrors the backend envelope: {"error": {code, message, details, request_id}}. */
const errorEnvelopeSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    details: z.unknown().optional(),
    request_id: z.string().nullable().optional(),
  }),
});

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;
  readonly requestId: string | null;

  constructor(status: number, code: string, message: string, details: unknown = {}, requestId: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }

  /** Field errors from a VALIDATION_ERROR response, e.g. {"amount": ["..."]}. */
  get fieldErrors(): Record<string, string[]> {
    if (this.code !== "VALIDATION_ERROR" || typeof this.details !== "object" || this.details === null) return {};
    const result: Record<string, string[]> = {};
    for (const [field, value] of Object.entries(this.details)) {
      if (Array.isArray(value)) result[field] = value.map(String);
    }
    return result;
  }
}

export const NETWORK_ERROR_MESSAGE = "تعذّر الاتصال بالخادم. تحقّق من الاتصال وحاول مجدداً.";
const UNKNOWN_ERROR_MESSAGE = "حدث خطأ غير متوقع. حاول مرة أخرى لاحقاً.";

export async function toApiError(response: Response): Promise<ApiError> {
  const requestId = response.headers.get("X-Request-ID");
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    // Non-JSON error (e.g. a proxy page) — fall through to the generic error.
  }
  const parsed = errorEnvelopeSchema.safeParse(body);
  if (parsed.success) {
    const { code, message, details, request_id } = parsed.data.error;
    return new ApiError(response.status, code, message, details ?? {}, request_id ?? requestId);
  }
  return new ApiError(response.status, "HTTP_ERROR", UNKNOWN_ERROR_MESSAGE, {}, requestId);
}
