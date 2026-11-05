"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";

import { ResponsiveImage } from "@/components/art/ResponsiveImage";
import { Alert } from "@/components/ui/Alert";
import { Icon } from "@/components/ui/Icon";
import { StatusBadge, type Tone } from "@/components/ui/StatusBadge";
import { Link } from "@/i18n/navigation";
import { formatDateTime } from "@/lib/formatters/datetime";
import { formatUsd } from "@/lib/formatters/money";

import { listMyBids, myBidsKey, type MyBidAuction } from "./api";

type MyStatus = "highest" | "outbid" | "closing" | "pending_payment" | "won" | "lost" | "unpaid" | "cancelled";
const TONE: Record<MyStatus, Tone> = {
  pending_payment: "action",
  outbid: "action",
  highest: "success",
  won: "success",
  closing: "progress",
  lost: "closed",
  unpaid: "closed",
  cancelled: "closed",
};

function Row({ auction }: { auction: MyBidAuction }) {
  const t = useTranslations("auctions");
  const status = auction.my_status as MyStatus;
  const actionable = status === "pending_payment" || status === "outbid";
  return (
    <li
      className={`flex flex-wrap items-center gap-4 rounded-[var(--radius-card)] border p-4 sm:flex-nowrap ${
        actionable ? "border-secondary/60 bg-white/70" : "border-border/60"
      }`}
    >
      <div className="size-20 shrink-0 overflow-hidden rounded-[var(--radius-card)] bg-surface/60 p-2">
        {auction.image ? <ResponsiveImage image={auction.image.image} alt={auction.title} sizes="5rem" /> : null}
      </div>
      <div className="min-w-0 flex-1">
        <Link href={`/auctions/${auction.id}`} className="font-medium text-primary hover:text-secondary">
          {auction.title}
        </Link>
        <p className="mt-1 text-sm text-muted">
          {t("mine.myTop", { amount: formatUsd(auction.my_top_bid) })}
          {auction.current_price ? (
            <>
              {" · "}
              {t("card.current")} <bdi dir="ltr">{formatUsd(auction.current_price)}</bdi>
            </>
          ) : null}
        </p>
        <p className="mt-1 text-xs text-muted">
          {status === "highest" || status === "outbid"
            ? t("countdown.endsAt", { date: formatDateTime(auction.ends_at) })
            : t("card.endedOn", { date: formatDateTime(auction.ends_at) })}
        </p>
      </div>
      <div className="flex w-full items-center justify-between gap-3 sm:w-auto sm:flex-col sm:items-end">
        <StatusBadge tone={TONE[status] ?? "progress"}>{t(`mine.status.${status}`)}</StatusBadge>
        {status === "pending_payment" && auction.order_number ? (
          <Link
            href={`/orders/${auction.order_number}`}
            className="inline-flex min-h-10 items-center rounded-[var(--radius-control)] bg-primary px-4 text-sm font-medium text-on-primary hover:bg-primary/90"
          >
            {t("mine.payNow")}
          </Link>
        ) : null}
        {status === "won" && auction.order_number ? (
          <Link href={`/orders/${auction.order_number}`} className="text-sm text-primary underline-offset-4 hover:underline">
            {t("result.viewOrder")}
          </Link>
        ) : null}
      </div>
    </li>
  );
}

/** The bidder's auctions, actionable first (pay a won deposit, then outbid positions). */
export function MyBidsList() {
  const t = useTranslations("auctions.mine");
  const tc = useTranslations("common");
  const ta = useTranslations("auctions");
  const bids = useQuery({ queryKey: myBidsKey, queryFn: listMyBids, refetchInterval: 30_000 });

  if (bids.isPending) {
    return (
      <div className="flex flex-col gap-4" aria-busy>
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-28 animate-pulse rounded-[var(--radius-card)] bg-surface/60" />
        ))}
      </div>
    );
  }
  if (bids.isError) {
    return (
      <Alert tone="error">
        {tc("loadError")}{" "}
        <button type="button" className="underline" onClick={() => void bids.refetch()}>
          {tc("retry")}
        </button>
      </Alert>
    );
  }
  if (bids.data.length === 0) {
    return (
      <div className="flex flex-col items-center gap-3 py-16 text-center">
        <Icon name="clock" className="size-12 text-secondary" />
        <p className="text-lg text-primary">{t("empty")}</p>
        <p className="max-w-sm text-sm text-muted">{t("emptyHint")}</p>
        <Link
          href="/auctions"
          className="mt-2 inline-flex min-h-11 items-center rounded-[var(--radius-control)] bg-primary px-6 text-sm font-medium text-on-primary hover:bg-primary/90"
        >
          {ta("title")}
        </Link>
      </div>
    );
  }
  return (
    <ul className="flex flex-col gap-4">
      {bids.data.map((auction) => (
        <Row key={auction.id} auction={auction} />
      ))}
    </ul>
  );
}
