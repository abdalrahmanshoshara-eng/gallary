"use client";

import { useTranslations } from "next-intl";

import { formatCountdown } from "@/lib/formatters/datetime";

import { useServerNow } from "./useAuctionLive";

const DAY = 24 * 3600 * 1000;

export function remainingLabel(ms: number, t: (key: "days", values: { days: number; hours: number }) => string): string {
  if (ms >= DAY) {
    const days = Math.floor(ms / DAY);
    return t("days", { days, hours: Math.floor((ms % DAY) / 3_600_000) });
  }
  return formatCountdown(ms);
}

/**
 * Time left until `deadline` by the server clock. Re-renders only itself every second and is
 * not announced by screen readers on each tick (the deadline is stated in text instead).
 */
export function AuctionCountdown({
  deadline,
  serverNow,
  urgentBelowMs = 5 * 60 * 1000,
  className = "",
}: {
  deadline: string;
  serverNow: () => number;
  urgentBelowMs?: number;
  className?: string;
}) {
  const t = useTranslations("auctions.countdown");
  const now = useServerNow(serverNow);
  const left = Math.max(0, Date.parse(deadline) - now);
  const urgent = left > 0 && left < urgentBelowMs;
  return (
    <span role="timer" aria-live="off" dir={left >= DAY ? "rtl" : "ltr"} className={`tabular-nums ${urgent ? "text-primary" : ""} ${className}`}>
      {remainingLabel(left, t)}
    </span>
  );
}
