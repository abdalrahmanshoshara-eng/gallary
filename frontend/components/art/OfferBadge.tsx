import { getTranslations } from "next-intl/server";

import type { Offer } from "@/lib/catalog/types";
import { formatUsd } from "@/lib/formatters/money";

type Reason = "sold_out" | "reserved" | "not_started" | "ended" | "artwork_unavailable" | "not_active" | "quantity_limit" | "insufficient_stock" | "auction_only";

/** One line under a card: the price when it can be bought, otherwise why not. */
export async function OfferBadge({ offer }: { offer: Offer | null | undefined }) {
  if (!offer) return null;
  const t = await getTranslations("catalog.offer");
  if (offer.purchasable && offer.price_usd) {
    return (
      <p className="mt-2 font-medium text-primary">
        <bdi dir="ltr">{formatUsd(offer.price_usd)}</bdi>
      </p>
    );
  }
  const reason = (offer.unavailable_reason ?? "not_active") as Reason;
  return (
    <p className="mt-2 text-sm text-muted">
      {offer.price_usd && reason !== "sold_out" ? <bdi dir="ltr">{formatUsd(offer.price_usd)} · </bdi> : null}
      {t(`status.${reason}`)}
    </p>
  );
}
