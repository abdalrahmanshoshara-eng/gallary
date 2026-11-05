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

/** Offset of Damascus time from UTC at `date`, in minutes (from the time-zone database). */
function damascusOffsetMinutes(date: Date): number {
  const part = new Intl.DateTimeFormat("en-US", { timeZone: DISPLAY_TIME_ZONE, timeZoneName: "longOffset" })
    .formatToParts(date)
    .find((p) => p.type === "timeZoneName")?.value;
  const match = /GMT([+-])(\d{2}):?(\d{2})?/.exec(part ?? "");
  if (!match) return 0;
  const minutes = Number(match[2]) * 60 + Number(match[3] ?? 0);
  return match[1] === "-" ? -minutes : minutes;
}

/** ISO instant → "YYYY-MM-DDTHH:mm" in Damascus time, for <input type="datetime-local">. */
export function toDamascusInput(iso: string): string {
  const date = new Date(iso);
  const local = new Date(date.getTime() + damascusOffsetMinutes(date) * 60_000);
  return local.toISOString().slice(0, 16);
}

/** "YYYY-MM-DDTHH:mm" typed in Damascus time → ISO instant (UTC). */
export function fromDamascusInput(value: string): string | null {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) return null;
  const asUtc = new Date(`${value}:00Z`);
  if (Number.isNaN(asUtc.getTime())) return null;
  const guess = new Date(asUtc.getTime() - damascusOffsetMinutes(asUtc) * 60_000);
  // Re-check at the resulting instant (offset changes across DST boundaries).
  return new Date(asUtc.getTime() - damascusOffsetMinutes(guess) * 60_000).toISOString();
}
