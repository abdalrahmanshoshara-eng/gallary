export type BackoffOptions = { baseMs: number; maxMs: number };

export const DEFAULT_BACKOFF: BackoffOptions = { baseMs: 1_000, maxMs: 30_000 };

/**
 * Exponential backoff with "full jitter": a random delay in [0, min(max, base·2^attempt)].
 * Jitter spreads reconnects after a redeploy so instances are not hit all at once.
 */
export function backoffDelay(attempt: number, options: BackoffOptions = DEFAULT_BACKOFF, random = Math.random): number {
  const ceiling = Math.min(options.maxMs, options.baseMs * 2 ** Math.max(0, attempt));
  return Math.round(random() * ceiling);
}
