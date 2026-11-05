import { formatUsd } from "@/lib/formatters/money";

type Translate = (key: "window" | "hour", values: Record<string, number>) => string;

/** "ساعة" / "5 دقائق" from a duration in seconds (auction rules are whole minutes). */
export function durationText(seconds: number, t: Translate): string {
  if (seconds >= 3600 && seconds % 3600 === 0) return t("hour", { hours: seconds / 3600 });
  return t("window", { minutes: Math.round(seconds / 60) });
}

/** Winner deposit for an amount, as the server computes it (percent of the final price). */
export function depositFor(amount: string, percent: string): string {
  const value = (Number(amount) * Number(percent)) / 100;
  return formatUsd(Math.min(Number(amount), Math.round(value * 100) / 100));
}

/** "50.00" → "50" for percentages shown in sentences. */
export const percentText = (value: string) => String(Number(value));
