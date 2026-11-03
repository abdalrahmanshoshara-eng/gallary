/** Dates are stored in UTC and always displayed in Damascus time. */
export const DISPLAY_TIME_ZONE = "Asia/Damascus";

const dateTime = new Intl.DateTimeFormat("ar-SY-u-nu-latn", {
  timeZone: DISPLAY_TIME_ZONE,
  dateStyle: "long",
  timeStyle: "short",
});

export function formatDateTime(value: string | Date): string {
  const date = typeof value === "string" ? new Date(value) : value;
  if (Number.isNaN(date.getTime())) throw new RangeError(`invalid date: ${String(value)}`);
  return dateTime.format(date);
}

/** Remaining time as h:mm:ss (or m:ss under an hour); never negative. */
export function formatCountdown(remainingMs: number): string {
  const total = Math.max(0, Math.floor(remainingMs / 1000));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const pad = (n: number) => n.toString().padStart(2, "0");
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`;
}
