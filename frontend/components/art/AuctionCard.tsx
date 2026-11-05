import { getTranslations } from "next-intl/server";

import { StatusBadge } from "@/components/ui/StatusBadge";
import { Link } from "@/i18n/navigation";
import type { Schema } from "@/lib/api/types";
import { formatDateTime } from "@/lib/formatters/datetime";
import { formatUsd } from "@/lib/formatters/money";

import { ResponsiveImage } from "./ResponsiveImage";

export type AuctionCardData = Schema<"AuctionCard">;
export type AuctionWindow = "live" | "upcoming" | "ended";

/**
 * An auction in a list. Times are absolute (correct even from a cached page); the live
 * countdown, price stream and bidding live on the auction's own page.
 */
export async function AuctionCard({ auction, window, priority = false }: { auction: AuctionCardData; window: AuctionWindow; priority?: boolean }) {
  const t = await getTranslations("auctions");
  const ts = await getTranslations("status_auction");
  const hasBids = auction.current_price !== null;
  const priceLabel = window === "ended" ? t("card.final") : hasBids ? t("card.current") : t("card.opening");
  const price = auction.current_price ?? auction.starting_price;
  const showPrice = window !== "ended" || (hasBids && auction.outcome === "sold");
  return (
    <article className="group">
      <Link href={`/auctions/${auction.id}`} className="block">
        <div className="relative flex aspect-[4/5] items-center justify-center overflow-hidden rounded-[var(--radius-card)] bg-surface/60 p-4 transition-colors duration-500 ease-calm group-hover:bg-surface">
          {auction.image ? (
            <ResponsiveImage
              image={auction.image.image}
              alt={auction.image.alt_text || auction.title}
              sizes="(min-width: 1280px) 22vw, (min-width: 768px) 30vw, 90vw"
              priority={priority}
            />
          ) : null}
          {window === "live" ? (
            <span className="absolute start-3 top-3 inline-flex items-center gap-1.5 rounded-full bg-primary px-3 py-1 text-xs font-medium text-on-primary">
              <span className="size-1.5 rounded-full bg-on-primary motion-safe:animate-pulse" aria-hidden />
              {t("tabs.live")}
            </span>
          ) : null}
        </div>
        <h3 className="mt-4 font-heading text-lg text-primary group-hover:text-secondary">{auction.title}</h3>
      </Link>
      <p className="mt-1 text-sm text-muted">{auction.creator_name}</p>
      <div className="mt-3 flex flex-wrap items-baseline justify-between gap-2">
        {showPrice ? (
          <p>
            <span className="text-xs text-muted">{priceLabel} </span>
            <bdi dir="ltr" className="font-medium text-primary">
              {formatUsd(price)}
            </bdi>
          </p>
        ) : (
          <StatusBadge tone="closed">{ts(auction.status)}</StatusBadge>
        )}
        <p className="text-xs text-muted">{t("card.bids", { count: auction.bid_count })}</p>
      </div>
      <p className="mt-1 text-xs text-muted">
        {window === "upcoming"
          ? t("card.startsOn", { date: formatDateTime(auction.starts_at) })
          : window === "live"
            ? t("countdown.endsAt", { date: formatDateTime(auction.ends_at) })
            : t("card.endedOn", { date: formatDateTime(auction.ends_at) })}
      </p>
    </article>
  );
}
