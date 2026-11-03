/**
 * Validates a post-login redirect target. Only same-site absolute paths are allowed, so
 * `?next=` cannot be abused as an open redirect (`//evil.com`, `https://…`, `/\\evil`).
 */
export function safeNextPath(value: string | null | undefined, fallback = "/account"): string {
  if (!value || value.length > 512) return fallback;
  if (!value.startsWith("/") || value.startsWith("//") || value.startsWith("/\\")) return fallback;
  if (/[\u0000-\u001f]/.test(value)) return fallback;
  if (value.startsWith("/api/") || value.startsWith("/ws/")) return fallback;
  return value;
}
