"use client";

import { useTranslations } from "next-intl";
import { useEffect, useMemo } from "react";

import { Alert } from "@/components/ui/Alert";
import { StatusBadge, type Tone } from "@/components/ui/StatusBadge";
import { Link } from "@/i18n/navigation";
import { formatDateTime } from "@/lib/formatters/datetime";
import { formatUsd } from "@/lib/formatters/money";

import type { AuctionDetail } from "./api";
import { AuctionCountdown } from "./AuctionCountdown";
import { BidPanel } from "./BidPanel";
import { depositFor, durationText } from "./format";
import { phaseOf, type AuctionState, type Phase } from "./live";
import { useAuctionLive, useServerNow } from "./useAuctionLive";

const PHASE_TONE: Record<Phase, Tone> = {
  upcoming: "progress",
  live: "action",
  closing: "action",
  pending_payment: "progress",
  ended: "closed",
  cancelled: "closed",
};

const primaryLink =
  "inline-flex min-h-12 w-full items-center justify-center rounded-[var(--radius-control)] bg-primary px-6 font-medium text-on-primary transition-colors duration-300 ease-calm hover:bg-primary/90 sm:w-auto";

/** Initial render before the first REST snapshot arrives: the cached public detail. */
function fromDetail(detail: AuctionDetail): AuctionState {
  return {
    seq: detail.version,
    server_time: new Date().toISOString(),
    status: detail.status,
    outcome: detail.outcome ?? "",
    current_price: detail.current_price,
    minimum_next_bid: detail.minimum_next_bid,
    bid_count: detail.bid_count,
    starts_at: detail.starts_at,
    ends_at: detail.ends_at,
    extensions_count: detail.extensions_count,
    reserve_met: detail.reserve_met,
    payment_deadline: null,
    winner_alias: null,
    bids: [],
    me: null,
  };
}

function ConnectionBadge({ status }: { status: string }) {
  const t = useTranslations("auctions.connection");
  if (status !== "reconnecting" && status !== "closed") return null;
  return (
    <p role="status" className="flex items-center gap-2 rounded-[var(--radius-control)] bg-secondary/10 px-3 py-2 text-xs text-text">
      <span className="size-2 animate-pulse rounded-full bg-secondary motion-reduce:animate-none" aria-hidden />
      {t(status)}
    </p>
  );
}

function Result({ detail, state, phase, serverNow }: { detail: AuctionDetail; state: AuctionState; phase: Phase; serverNow: () => number }) {
  const t = useTranslations("auctions.result");
  const me = state.me;
  const price = state.current_price ? formatUsd(state.current_price) : "";
  if (phase === "cancelled") return <Alert tone="info">{t("cancelled")}</Alert>;
  if (phase === "pending_payment") {
    if (me?.is_winner && state.payment_deadline) {
      return (
        <section aria-labelledby="won-title" className="rounded-[var(--radius-card)] border border-secondary/60 bg-white/80 p-5">
          <h2 id="won-title" className="text-xl font-semibold text-primary">
            {t("wonTitle")}
          </h2>
          <p className="mt-2 text-sm text-text">
            {t("wonBody", { deposit: depositFor(state.current_price ?? "0", detail.winner_deposit_percent) })}
          </p>
          <p className="mt-4 text-sm text-muted">{t("payWithin")}</p>
          <AuctionCountdown deadline={state.payment_deadline} serverNow={serverNow} className="text-2xl font-semibold" urgentBelowMs={15 * 60 * 1000} />
          {me.order_number ? (
            <div className="mt-5">
              <Link href={`/orders/${me.order_number}`} className={primaryLink}>
                {t("payNow")}
              </Link>
            </div>
          ) : null}
        </section>
      );
    }
    return (
      <Alert tone="info">
        {t("pendingOther", { amount: price, alias: state.winner_alias ?? 0 })}
        {me?.alias ? ` ${t("lost")}` : ""}
      </Alert>
    );
  }
  if (phase !== "ended") return null;
  if (state.outcome === "sold" && me?.is_winner) {
    return (
      <Alert tone="success">
        {t("awardedMine")}{" "}
        {me.order_number ? (
          <Link href={`/orders/${me.order_number}`} className="font-medium underline">
            {t("viewOrder")}
          </Link>
        ) : null}
      </Alert>
    );
  }
  const outcome = (state.outcome || "no_sale") as "sold" | "no_sale" | "reserve_not_met" | "unpaid";
  return (
    <Alert tone="info">
      {t(outcome, { amount: price })}
      {me?.alias && outcome === "sold" ? ` ${t("lost")}` : ""}
    </Alert>
  );
}

function BidHistory({ state }: { state: AuctionState }) {
  const t = useTranslations("auctions.history");
  const mine = state.me?.alias ?? null;
  return (
    <section aria-labelledby="bid-history">
      <h2 id="bid-history" className="mb-3 text-lg font-medium text-primary">
        {t("title")}
      </h2>
      {state.bids.length === 0 ? (
        <p className="text-sm text-muted">{t("empty")}</p>
      ) : (
        <ol className="divide-y divide-border/50 border-y border-border/50">
          {state.bids.map((bid, index) => (
            <li key={bid.id} className={`flex items-center justify-between gap-4 py-3 text-sm ${index === 0 ? "font-medium" : ""}`}>
              <span className="flex items-center gap-2">
                <span className={bid.alias === mine ? "text-primary" : "text-text"}>
                  {bid.alias === mine ? t("you") : t("bidder", { alias: bid.alias })}
                </span>
                {index === 0 ? <span className="rounded-full bg-secondary/15 px-2 py-0.5 text-[11px] text-primary">{t("top")}</span> : null}
              </span>
              <span className="flex items-center gap-4">
                <time dateTime={bid.created_at} className="text-xs text-muted">
                  {formatDateTime(bid.created_at)}
                </time>
                <bdi dir="ltr" className="tabular-nums">
                  {formatUsd(bid.amount)}
                </bdi>
              </span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

/**
 * The live part of an auction page: price, countdown, bidding and history, kept current by
 * the auction's stream. Announces new prices politely and personal changes assertively.
 */
export function AuctionLive({ detail }: { detail: AuctionDetail }) {
  const t = useTranslations("auctions");
  const ts = useTranslations("auctions.phase");
  const { query, connection, lastEvent, serverNow, acceptState } = useAuctionLive(detail.id);
  const state = query.data ?? fromDetail(detail);
  const now = useServerNow(serverNow, 1000);
  const phase = phaseOf(state, now);
  const { refetch } = query;

  // Until the server's result arrives, re-check a closing auction every few seconds.
  useEffect(() => {
    if (phase !== "closing") return;
    const timer = setInterval(() => void refetch(), 3000);
    return () => clearInterval(timer);
  }, [phase, refetch]);

  const announcement = useMemo(() => {
    if (!lastEvent) return { polite: "", assertive: "" };
    const event = lastEvent.event;
    if (event.type === "bid") {
      const amount = formatUsd(event.bid.amount);
      const outbidMe = !event.mine && state.me?.alias && state.me.my_top_bid;
      return {
        polite: event.mine ? "" : t("announce.newBid", { amount }),
        assertive: outbidMe ? t("announce.outbid", { amount }) : "",
      };
    }
    if (event.type === "voided") {
      return { polite: t("announce.voided", { amount: formatUsd(state.current_price ?? detail.starting_price) }), assertive: "" };
    }
    if (event.type === "status" && (event.status === "ended" || event.status === "pending_winner_payment")) {
      return { polite: t("announce.ended"), assertive: "" };
    }
    return { polite: "", assertive: "" };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- announce once per event
  }, [lastEvent]);

  const hasBids = state.current_price !== null;
  const priceLabel = phase === "ended" || phase === "pending_payment" ? t("price.final") : hasBids ? t("price.current") : t("price.opening");
  const shownPrice = state.current_price ?? detail.starting_price;
  const counting = phase === "upcoming" || phase === "live";

  return (
    <div className="flex flex-col gap-6">
      <div className="sr-only" aria-live="polite">
        {announcement.polite}
      </div>
      <div className="sr-only" aria-live="assertive">
        {announcement.assertive}
      </div>

      <div className="rounded-[var(--radius-card)] border border-border/60 bg-white/60 p-5 md:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <StatusBadge tone={PHASE_TONE[phase]}>{ts(phase)}</StatusBadge>
          <ConnectionBadge status={connection} />
        </div>

        <div className="mt-5 flex flex-wrap items-end justify-between gap-6">
          <div>
            <p className="text-sm text-muted">{priceLabel}</p>
            <bdi
              key={state.seq}
              dir="ltr"
              className="block text-4xl font-semibold text-primary tabular-nums rounded-[var(--radius-control)] motion-safe:animate-[price-flash_1.2s_ease-out]"
            >
              {formatUsd(shownPrice)}
            </bdi>
            <p className="mt-1 text-sm text-muted">
              {t("price.bids", { count: state.bid_count })}
              {state.reserve_met !== null && hasBids && (phase === "live" || phase === "closing") ? (
                <span className={state.reserve_met ? "text-olive" : ""}>
                  {" · "}
                  {state.reserve_met ? t("price.reserveMet") : t("price.reserveNotMet")}
                </span>
              ) : null}
            </p>
          </div>
          {counting ? (
            <div className="text-end">
              <p className="text-sm text-muted">{phase === "upcoming" ? t("countdown.startsIn") : t("countdown.endsIn")}</p>
              <AuctionCountdown
                deadline={phase === "upcoming" ? state.starts_at : state.ends_at}
                serverNow={serverNow}
                className="text-2xl font-semibold"
              />
              <p className="mt-1 text-xs text-muted">
                {phase === "upcoming"
                  ? t("countdown.startsAt", { date: formatDateTime(state.starts_at) })
                  : t("countdown.endsAt", { date: formatDateTime(state.ends_at) })}
              </p>
            </div>
          ) : null}
        </div>

        {phase === "live" && state.extensions_count > 0 ? (
          <div className="mt-4">
            <Alert tone="info">
              {t("countdown.extended", {
                duration: durationText(detail.extension_duration_sec, t),
                date: formatDateTime(state.ends_at),
              })}
            </Alert>
          </div>
        ) : null}

        {phase === "live" || phase === "upcoming" ? (
          <p className="mt-4 border-t border-border/50 pt-4 text-sm text-text">
            {t("price.minimumNext")}:{" "}
            <bdi dir="ltr" className="font-medium tabular-nums">
              {formatUsd(state.minimum_next_bid)}
            </bdi>
          </p>
        ) : null}

        <div className="mt-5">
          {phase === "live" || phase === "upcoming" || phase === "closing" ? (
            <BidPanel detail={detail} state={state} phase={phase} onAccepted={acceptState} onStale={() => void refetch()} />
          ) : (
            <Result detail={detail} state={state} phase={phase} serverNow={serverNow} />
          )}
        </div>
      </div>

      <BidHistory state={state} />
    </div>
  );
}
