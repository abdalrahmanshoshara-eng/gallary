import { DISPLAY_TIME_ZONE, formatDateTime } from "@/lib/formatters/datetime";

const relative = new Intl.RelativeTimeFormat("ar-u-nu-latn", {
  numeric: "auto",
});
const dayKeyFormat = new Intl.DateTimeFormat("en-CA", {
  timeZone: DISPLAY_TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});
const dayLabel = new Intl.DateTimeFormat("ar-SY-u-nu-latn", {
  timeZone: DISPLAY_TIME_ZONE,
  weekday: "long",
  day: "numeric",
  month: "long",
});

/** "منذ 5 دقائق" within a day, then the full date and time. */
export function notificationTime(iso: string, now: Date = new Date()): string {
  const seconds = Math.round((new Date(iso).getTime() - now.getTime()) / 1000);
  if (seconds > -60) return relative.format(0, "second");
  if (seconds > -3600)
    return relative.format(Math.round(seconds / 60), "minute");
  if (seconds > -86_400)
    return relative.format(Math.round(seconds / 3600), "hour");
  return formatDateTime(iso);
}

/** Day heading in Damascus time: "اليوم", "أمس", or "الأحد 8 تشرين الثاني". */
export function dayHeading(
  iso: string,
  now: Date = new Date(),
): { key: string; label: string } {
  const key = dayKeyFormat.format(new Date(iso));
  const today = dayKeyFormat.format(now);
  const yesterday = dayKeyFormat.format(new Date(now.getTime() - 86_400_000));
  const label =
    key === today
      ? "today"
      : key === yesterday
        ? "yesterday"
        : dayLabel.format(new Date(iso));
  return { key, label };
}
